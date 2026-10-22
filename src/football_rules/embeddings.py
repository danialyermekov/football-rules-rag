"""Local dense BGE-M3 embeddings; no paid API or silent token truncation."""

from importlib.metadata import version
from pathlib import Path
from typing import Protocol

MODEL_ID = "BAAI/bge-m3"
MODEL_REVISION = "5617a9f61b028005a4858fdac845db406aefb181"


class Embedder(Protocol):
    dimension: int

    def encode(self, texts: list[str]) -> list[list[float]]: ...

    def parameters(self) -> dict[str, object]: ...


class BGEEmbedder:
    dimension = 1024

    def __init__(self, model_path: Path = Path("data/models/bge-m3")) -> None:
        if not (model_path / "config.json").is_file():
            raise ValueError(
                "Download the pinned BGE-M3 model first; see docs/retrieval.md"
            )

        for filename in ("pytorch_model.bin", "config.json", "tokenizer.json"):
            metadata = (
                model_path / ".cache/huggingface/download" / f"{filename}.metadata"
            )

            if (
                not (model_path / filename).is_file()
                or not metadata.exists()
                or metadata.read_text(encoding="utf-8").splitlines()[:1]
                != [MODEL_REVISION]
            ):
                raise ValueError(
                    "Model files must be downloaded from the pinned revision"
                )

        import torch
        from sentence_transformers import SentenceTransformer

        torch.set_num_threads(4)
        self.model = SentenceTransformer(
            str(model_path), device="cpu", local_files_only=True
        )
        limit = self.model.max_seq_length

        if limit is None:
            raise ValueError("Embedding model must declare its token limit")

        self.max_tokens = limit
        self.batch_size = 4

    def parameters(self) -> dict[str, object]:
        return {
            "model": MODEL_ID,
            "revision": MODEL_REVISION,
            "dimension": self.dimension,
            "normalize_embeddings": True,
            "device": "cpu",
            "dtype": "float32",
            "batch_size": self.batch_size,
            "max_seq_length": self.max_tokens,
            "sentence_transformers": version("sentence-transformers"),
            "torch": version("torch"),
        }

    def encode(self, texts: list[str]) -> list[list[float]]:
        if not texts or any(not text.strip() for text in texts):
            raise ValueError("Embedding input must contain nonempty texts")

        tokens = self.model.tokenizer(texts, padding=False, truncation=False)[
            "input_ids"
        ]

        if any(len(row) > self.max_tokens for row in tokens):
            raise ValueError("Embedding input exceeds model token limit")

        encoded = self.model.encode(
            texts,
            batch_size=self.batch_size,
            normalize_embeddings=True,
            show_progress_bar=len(texts) > self.batch_size,
            convert_to_numpy=True,
        )
        vectors: list[list[float]] = encoded.tolist()
        return vectors
