"""Pinned multilingual cross-encoder; full query/passage pairs, no truncation."""

import math
from importlib.metadata import version
from pathlib import Path
from typing import Any

import mlflow

MODEL_ID = "BAAI/bge-reranker-v2-m3"
MODEL_REVISION = "953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e"


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


class CrossEncoderReranker:
    def __init__(
        self,
        device: str = "cuda",
        model_path: Path = Path("data/models/bge-reranker-v2-m3"),
    ) -> None:
        if device not in {"cpu", "cuda"}:
            raise ValueError("Reranker device must be cpu/cuda")

        for name in (
            "config.json",
            "model.safetensors",
            "tokenizer.json",
            "tokenizer_config.json",
            "special_tokens_map.json",
        ):
            metadata = model_path / ".cache/huggingface/download" / f"{name}.metadata"
            if (
                not (model_path / name).is_file()
                or not metadata.is_file()
                or metadata.read_text(encoding="utf-8").splitlines()[:1]
                != [MODEL_REVISION]
            ):
                raise ValueError("Download the pinned reranker revision; see README")

        import torch
        from sentence_transformers import CrossEncoder

        if device == "cuda" and not torch.cuda.is_available():
            raise ValueError(
                "CUDA is unavailable; use uv run --extra cuda or device cpu"
            )

        torch.set_num_threads(4)
        self.device = device
        self.max_tokens = 1024
        self.batch_size = 2
        self.model = CrossEncoder(
            str(model_path),
            device=device,
            max_length=self.max_tokens,
            local_files_only=True,
            model_kwargs={"dtype": torch.float32},
            activation_fn=torch.nn.Identity(),
        )

    def parameters(self) -> dict[str, object]:
        import torch

        return {
            "model": MODEL_ID,
            "revision": MODEL_REVISION,
            "device": self.device,
            "dtype": "float32",
            "batch_size": self.batch_size,
            "max_pair_tokens": self.max_tokens,
            "truncation": "reject_overflow",
            "scores": "raw_logits",
            "torch": version("torch"),
            "cuda_runtime": str(torch.version.cuda),
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
        )
        return rank_documents(documents, [float(score) for score in scores])
