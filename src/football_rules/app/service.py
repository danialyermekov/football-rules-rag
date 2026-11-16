"""Application service orchestrating retrieval, reranking, packing, and generation."""

import os
from pathlib import Path
from typing import Any, Self

from dotenv import load_dotenv
from google import genai
from google.genai import types

from football_rules.config import (
    DEFAULT_ASK_EMBEDDING,
    DEFAULT_BRANCH_DEPTH,
    DEFAULT_CHUNKS_PATH,
    DEFAULT_CONTEXT_BUDGET,
    DEFAULT_DEVICE,
    DEFAULT_QDRANT_PATH,
    SUPPORTED_LANGUAGES,
    SUPPORTED_MODELS,
)
from football_rules.evaluation.tracking import configure_tracking
from football_rules.generation.gemini import generate_answer, valid_citations
from football_rules.retrieval.bm25 import BM25Retriever
from football_rules.retrieval.context import pack_context
from football_rules.retrieval.embeddings import QWEN_MODEL_ID, load_embedder
from football_rules.retrieval.hybrid import HybridRetriever
from football_rules.retrieval.reranking import CrossEncoderReranker
from football_rules.retrieval.store import DenseRetriever, resolve_collection


def generation_options(model: str) -> dict[str, Any]:
    """Return model-specific Gemini decoding parameters."""
    if model not in SUPPORTED_MODELS:
        raise ValueError(f"Unsupported model: {model}")

    if model == "gemini-3.8-flash":
        return {"thinking_level": types.ThinkingLevel.LOW, "max_output_tokens": 2048}

    if model == "gemini-4-argon":
        return {
            "thinking_level": types.ThinkingLevel.LOW,
            "max_output_tokens": 32768,
            "temperature": None,
        }

    return {}


def _serialize_options(options: dict[str, Any]) -> dict[str, Any]:
    serialized: dict[str, Any] = {}

    for key, value in options.items():
        if isinstance(value, types.ThinkingLevel):
            serialized[key] = value.name
        else:
            serialized[key] = value

    return serialized


class AskSession:
    """Reusable Hybrid retrieval + Gemini session that loads models and indexes once."""

    def __init__(
        self,
        database: Path = DEFAULT_QDRANT_PATH,
        collection: str | None = None,
        chunks_path: Path = DEFAULT_CHUNKS_PATH,
        *,
        rerank: bool = False,
        device: str = DEFAULT_DEVICE,
    ) -> None:
        self._api_key = self._load_api_key()
        self.database = database
        self.collection = resolve_collection(database, collection, QWEN_MODEL_ID)
        self.chunks_path = chunks_path
        self.rerank = rerank

        configure_tracking()

        self.embedder = load_embedder(DEFAULT_ASK_EMBEDDING, device=device)
        self.lexical = BM25Retriever(chunks_path)
        self.dense = DenseRetriever(database, self.collection, self.embedder)

        try:
            self.retriever = HybridRetriever(self.dense, self.lexical)
            self.reranker = (
                CrossEncoderReranker(device=device, model_name="qwen3-0.6b")
                if rerank
                else None
            )
        except Exception:
            self.dense.close()
            raise

        self._closed = False

    @staticmethod
    def _load_api_key() -> str:
        load_dotenv(".env")
        key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

        if not key:
            raise ValueError("Configure GEMINI_API_KEY in environment or .env")

        return key

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        if not self._closed:
            self._closed = True
            self.dense.close()

    def _count_tokens(self, text: str) -> int:
        counter = getattr(self.embedder, "count_tokens", None)

        if callable(counter):
            return int(counter(text))

        return len(text.split())

    def _retrieve_context(self, query: str, language: str) -> dict[str, Any]:
        documents = self.retriever.search(query, language, DEFAULT_BRANCH_DEPTH)[
            :DEFAULT_BRANCH_DEPTH
        ]

        if self.reranker is not None:
            documents = self.reranker.rerank(query, documents)

        return pack_context(documents, DEFAULT_CONTEXT_BUDGET, self._count_tokens)

    def _generate(
        self,
        query: str,
        language: str,
        context_text: str,
        model: str,
        options: dict[str, Any],
    ) -> dict[str, Any]:
        timeout_ms = 900_000 if model == "gemini-4-argon" else 60_000
        http_options = types.HttpOptions(
            timeout=timeout_ms,
            retry_options=types.HttpRetryOptions(attempts=1),
        )

        with genai.Client(api_key=self._api_key, http_options=http_options) as client:
            return generate_answer(
                client,
                query,
                language,
                context_text,
                model=model,
                **options,
            )

    def ask(
        self,
        query: str,
        language: str = "ru",
        model: str = "gemini-2.5-flash-lite",
    ) -> dict[str, Any]:
        """Answer a single question using Hybrid retrieval and grounded Gemini."""
        if not query.strip() or language not in SUPPORTED_LANGUAGES:
            raise ValueError("Provide a nonempty question and language ru/en")

        options = generation_options(model)
        context = self._retrieve_context(query, language)
        output = self._generate(query, language, context["text"], model, options)

        output.update(
            {
                "question": query,
                "language": language,
                "requested_model": model,
                "context": context["text"],
                "context_token_count": context["token_count"],
                "documents": context["documents"],
                "settings": {
                    "database": str(self.database),
                    "collection": self.collection,
                    "chunks_path": str(self.chunks_path),
                    "embedding": DEFAULT_ASK_EMBEDDING,
                    "strategy": "hybrid+rerank" if self.rerank else "hybrid",
                    "rerank": self.rerank,
                    "candidate_depth": DEFAULT_BRANCH_DEPTH,
                    "token_budget": DEFAULT_CONTEXT_BUDGET,
                    "generation_options": _serialize_options(options),
                },
            }
        )
        output["citations_valid"] = valid_citations(output)
        return output


def ask_question(
    query: str,
    language: str,
    model: str,
    database: Path,
    collection: str | None = None,
    *,
    rerank: bool = False,
    device: str = DEFAULT_DEVICE,
) -> dict[str, Any]:
    """Convenience one-shot entrypoint that opens and closes an AskSession."""
    if not query.strip() or language not in SUPPORTED_LANGUAGES:
        raise ValueError("Provide a nonempty question and language ru/en")

    with AskSession(
        database=database, collection=collection, rerank=rerank, device=device
    ) as session:
        return session.ask(query, language, model)
