"""Ragas metrics using Gemini judges and the project's pinned local embeddings."""

import asyncio
import math
from typing import Any

import instructor
import mlflow
from google import genai
from google.genai import types
from ragas.embeddings.base import BaseRagasEmbedding
from ragas.llms import InstructorLLM

from football_rules.embeddings import Embedder


class LocalMetricEmbeddings(BaseRagasEmbedding):
    def __init__(self, embedder: Embedder) -> None:
        super().__init__()
        self.embedder = embedder

    def embed_text(self, text: str, **kwargs: Any) -> list[float]:
        return self.embedder.encode([text])[0]

    async def aembed_text(self, text: str, **kwargs: Any) -> list[float]:
        return self.embed_text(text)

    async def aembed_texts(self, texts: list[str], **kwargs: Any) -> list[list[float]]:
        return self.embedder.encode(texts)


def metric_applicability(name: str, documents: list[dict[str, Any]]) -> str | None:
    if not documents and name in {
        "context_precision",
        "context_recall",
        "faithfulness",
    }:
        return "No retrieved contexts; this Ragas metric rejects empty context lists"
    return None


def checked_score(value: Any, name: str) -> float | None:
    score = float(value)
    if math.isnan(score):
        return None
    lower = -1 if name == "answer_relevancy" else 0
    if not math.isfinite(score) or not lower <= score <= 1:
        raise ValueError(f"Invalid {name} score: {score}")
    return score


def evaluate_ragas_metric(
    metric_class: type[Any],
    name: str,
    api_key: str,
    model: str,
    *,
    metric_options: dict[str, Any] | None = None,
    **inputs: Any,
) -> dict[str, Any]:
    async def calculate() -> dict[str, Any]:
        client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(
                timeout=60000, retry_options=types.HttpRetryOptions(attempts=1)
            ),
        )
        async with client.aio:
            responses: list[dict[str, Any]] = []
            structured = instructor.from_genai(
                client, use_async=True, mode=instructor.Mode.JSON
            )
            structured.on(
                "completion:response",
                lambda response: responses.append(
                    response.model_dump(mode="json", exclude_none=True)
                ),
            )
            judge = InstructorLLM(
                client=structured,
                model=model,
                provider="google",
                temperature=0,
                max_tokens=2048,
                max_retries=1,
            )
            metric = metric_class(llm=judge, **(metric_options or {}))
            result = await metric.ascore(**inputs)
            score = checked_score(result.value, name)
            return {
                "value": score,
                "status": "undefined" if score is None else "ok",
                "reason": (
                    "Ragas returned NaN; inspect claim decomposition in judge responses"
                    if score is None
                    else result.reason
                ),
                "responses": responses,
            }

    # Explicit span inputs exclude the provider API key.
    with mlflow.start_span(name=f"ragas_{name}", span_type="CHAIN") as span:
        span.set_inputs({"metric": name, "model": model, **inputs})
        result = asyncio.run(calculate())
        span.set_outputs({"value": result["value"], "status": result["status"]})
        return result
