"""Pinned multilingual cross-encoder; full query/passage pairs, no truncation."""

import math
from importlib.metadata import version
from pathlib import Path
from typing import Any

import mlflow

from football_rules.retrieval.embeddings import (
    resolve_device,
    verify_pinned_model_files,
)

MODEL_ID = "BAAI/bge-reranker-v2-m3"
MODEL_REVISION = "953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e"
QWEN_MODEL_ID = "Qwen/Qwen3-Reranker-0.6B"
QWEN_REVISION = "e61197ed45024b0ed8a2d74b80b4d909f1255473"
QWEN_INSTRUCTION = (
    "Given a web search query, retrieve relevant passages that answer the query"
)


def rank_documents(
    documents: list[dict[str, Any]], scores: list[float]
) -> list[dict[str, Any]]:
    if len(scores) != len(documents) or not all(
        math.isfinite(score) for score in scores
    ):
        raise ValueError("Reranker must return one finite score per document")

    ranked = [
        {**document, "retrieval_score": document["score"], "score": score}
        for document, score in zip(documents, scores, strict=True)
    ]
    return sorted(ranked, key=lambda hit: (-hit["score"], hit["chunk_id"]))


def fuse_retrieval_reranker(
    documents: list[dict[str, Any]], reranked: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Equal RRF60 over retrieval and reranker ranks of the identical candidate pool."""
    identities = [hit["chunk_id"] for hit in documents]
    scored = {hit["chunk_id"]: hit for hit in reranked}
    if (
        len(set(identities)) != len(documents)
        or len(scored) != len(reranked)
        or set(identities) != set(scored)
    ):
        raise ValueError("Rank fusion requires identical unique candidate IDs")
    checked = rank_documents(documents, [scored[key]["score"] for key in identities])
    if [hit["chunk_id"] for hit in checked] != [hit["chunk_id"] for hit in reranked]:
        raise ValueError("Cached reranker order must match scores and tie-break")
    ranks = {hit["chunk_id"]: rank for rank, hit in enumerate(reranked, 1)}
    annotated = [
        {
            **hit,
            "retrieval_rank": rank,
            "reranker_rank": ranks[hit["chunk_id"]],
            "reranker_score": scored[hit["chunk_id"]]["score"],
        }
        for rank, hit in enumerate(documents, 1)
    ]
    scores = [
        1 / (60 + hit["retrieval_rank"]) + 1 / (60 + hit["reranker_rank"])
        for hit in annotated
    ]
    return rank_documents(annotated, scores)


class CrossEncoderReranker:
    def __init__(
        self,
        device: str = "auto",
        model_path: Path | None = None,
        *,
        model_name: str = "bge",
    ) -> None:
        if model_name not in {"bge", "qwen3-0.6b"}:
            raise ValueError("Reranker model must be bge/qwen3-0.6b")
        self.model_name = model_name
        self.model_id = MODEL_ID if model_name == "bge" else QWEN_MODEL_ID
        self.revision = MODEL_REVISION if model_name == "bge" else QWEN_REVISION
        if model_path is None:
            directory = (
                "bge-reranker-v2-m3" if model_name == "bge" else "qwen3-reranker-0.6b"
            )
            model_path = Path("data/models") / directory

        files = [
            "config.json",
            "model.safetensors",
            "tokenizer.json",
            "tokenizer_config.json",
        ]
        if model_name == "bge":
            files.append("special_tokens_map.json")
        else:
            files.extend(
                [
                    "config_sentence_transformers.json",
                    "modules.json",
                    "sentence_bert_config.json",
                    "chat_template.jinja",
                    "1_LogitScore/config.json",
                ]
            )
        verify_pinned_model_files(
            model_path,
            self.revision,
            files,
            "Download the pinned reranker revision; see README.md",
        )

        import torch
        from sentence_transformers import CrossEncoder

        resolved_device = resolve_device(device)
        torch.set_num_threads(4)
        self.device = resolved_device
        self.max_tokens = 1024
        self.batch_size = 2
        self.model = CrossEncoder(
            str(model_path),
            device=resolved_device,
            max_length=self.max_tokens,
            local_files_only=True,
            model_kwargs={"dtype": torch.float32},
            activation_fn=torch.nn.Identity(),
        )

    def parameters(self) -> dict[str, object]:
        import torch

        return {
            "model": self.model_id,
            "revision": self.revision,
            "device": self.device,
            "dtype": "float32",
            "batch_size": self.batch_size,
            "max_pair_tokens": self.max_tokens,
            "truncation": "reject_overflow",
            "scores": (
                "raw_logits" if self.model_name == "bge" else "yes_minus_no_logits"
            ),
            "instruction": ("none" if self.model_name == "bge" else QWEN_INSTRUCTION),
            "torch": version("torch"),
            "cuda_runtime": (
                str(torch.version.cuda) if self.device == "cuda" else "none"
            ),
            "gpu": torch.cuda.get_device_name(0) if self.device == "cuda" else "none",
            "sentence_transformers": version("sentence-transformers"),
        }

    @mlflow.trace(name="cross_encoder_reranking", span_type="RERANKER")
    def rerank(
        self, query: str, documents: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        if not query.strip() or any(
            not document["text"].strip() for document in documents
        ):
            raise ValueError("Provide a nonempty question and nonempty passage texts")
        if len({document["chunk_id"] for document in documents}) != len(documents):
            raise ValueError("Reranker candidates must have unique IDs")
        if not documents:
            return []

        pairs = [(query, document["text"]) for document in documents]
        prediction_kwargs: dict[str, Any] = {}
        if self.model_name == "qwen3-0.6b":
            # Count the actual chat template, including the instruction and answer suffix.
            prediction_kwargs = {
                "prompt": QWEN_INSTRUCTION,
                "processing_kwargs": {"text": {"truncation": False}},
            }
            features = self.model.preprocess(pairs, **prediction_kwargs)
            lengths = features["attention_mask"].sum(dim=1).tolist()
        else:
            lengths = [
                len(ids)
                for ids in self.model.tokenizer(pairs, truncation=False)["input_ids"]
            ]
        if max(lengths) > self.max_tokens:
            raise ValueError("Query/passage pair exceeds reranker token limit")

        scores = self.model.predict(
            pairs,
            batch_size=self.batch_size,
            show_progress_bar=False,
            convert_to_numpy=True,
            **prediction_kwargs,
        )
        return rank_documents(documents, [float(score) for score in scores])
