"""Pinned local embeddings with separate document and query encoding."""

from importlib.metadata import version
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

MODEL_ID = "BAAI/bge-m3"
MODEL_REVISION = "5617a9f61b028005a4858fdac845db406aefb181"
QWEN_MODEL_ID = "Qwen/Qwen3-Embedding-0.6B"
QWEN_MODEL_REVISION = "97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3"
E5_MODEL_ID = "intfloat/multilingual-e5-large"
E5_MODEL_REVISION = "3d7cfbdacd47fdda877c5cd8a79fbcc4f2a574f3"
QWEN_QUERY_PROMPT = (
    "Instruct: Given a web search query, retrieve relevant passages that answer the query"
    "\nQuery:"
)


def resolve_device(device: str = "auto") -> str:
    """Resolve auto/cpu/cuda into an available PyTorch device."""
    if device not in {"auto", "cpu", "cuda"}:
        raise ValueError("Device must be auto, cpu, or cuda")
    import torch

    cuda_available = torch.cuda.is_available()
    if device == "cuda" and not cuda_available:
        raise ValueError("CUDA was requested but is unavailable; use device 'cpu' or 'auto'")
    if device == "auto":
        return "cuda" if cuda_available else "cpu"
    return device


def verify_pinned_model_files(
    model_path: Path,
    revision: str,
    filenames: tuple[str, ...] | list[str],
    error_message: str,
) -> None:
    """Verify local Hugging Face weights/configs match the pinned commit revision."""
    for filename in filenames:
        metadata = model_path / ".cache/huggingface/download" / f"{filename}.metadata"
        if (
            not (model_path / filename).is_file()
            or not metadata.is_file()
            or metadata.read_text(encoding="utf-8").splitlines()[:1] != [revision]
        ):
            raise ValueError(error_message)


class Embedder(Protocol):
    dimension: int

    def encode(self, texts: list[str]) -> list[list[float]]: ...

    def encode_queries(self, texts: list[str]) -> list[list[float]]: ...

    def parameters(self) -> dict[str, object]: ...


class BGEEmbedder:
    dimension = 1024

    def __init__(
        self, model_path: Path = Path("data/models/bge-m3"), *, device: str = "cpu"
    ) -> None:
        if not (model_path / "config.json").is_file():
            raise ValueError(
                "Download the pinned BGE-M3 model first; see README.md"
            )

        verify_pinned_model_files(
            model_path,
            MODEL_REVISION,
            ("pytorch_model.bin", "config.json", "tokenizer.json"),
            "Model files must be downloaded from the pinned revision",
        )

        import torch
        from sentence_transformers import SentenceTransformer

        self.device = resolve_device(device)
        torch.set_num_threads(4)
        self.model = SentenceTransformer(
            str(model_path), device=self.device, local_files_only=True
        )
        limit = self.model.max_seq_length
        if limit is None:
            raise ValueError("Embedding model must declare its token limit")

        self.max_tokens = limit
        self.batch_size = 4

    def count_tokens(self, text: str) -> int:
        return len(self.model.tokenizer.encode(text, add_special_tokens=False))

    def parameters(self) -> dict[str, object]:
        return {
            "model": MODEL_ID,
            "revision": MODEL_REVISION,
            "dimension": self.dimension,
            "normalize_embeddings": True,
            "device": self.device,
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

    def encode_queries(self, texts: list[str]) -> list[list[float]]:
        return self.encode(texts)


class QwenEmbedder:
    """Use Qwen's published retrieval instruction only for queries."""

    dimension = 1024

    def __init__(
        self,
        model_path: Path = Path("data/models/qwen3-embedding-0.6b"),
        *,
        device: str = "auto",
    ) -> None:
        verify_pinned_model_files(
            model_path,
            QWEN_MODEL_REVISION,
            (
                "model.safetensors",
                "config.json",
                "tokenizer.json",
                "tokenizer_config.json",
                "config_sentence_transformers.json",
                "modules.json",
                "1_Pooling/config.json",
            ),
            "Download Qwen model files from the pinned revision",
        )

        import torch
        from sentence_transformers import SentenceTransformer

        self.device = resolve_device(device)
        torch.set_num_threads(4)
        self.model = SentenceTransformer(
            str(model_path),
            device=self.device,
            local_files_only=True,
            model_kwargs={"dtype": torch.float32, "attn_implementation": "sdpa"},
        )
        self.model.tokenizer.padding_side = "left"
        limit = self.model.max_seq_length
        if limit is None:
            raise ValueError("Embedding model must declare its token limit")

        self.max_tokens = limit
        self.batch_size = 2

    def count_tokens(self, text: str) -> int:
        return len(self.model.tokenizer.encode(text, add_special_tokens=False))

    def parameters(self) -> dict[str, object]:
        return {
            "model": QWEN_MODEL_ID,
            "revision": QWEN_MODEL_REVISION,
            "dimension": self.dimension,
            "normalize_embeddings": True,
            "device": self.device,
            "dtype": "float32",
            "batch_size": self.batch_size,
            "max_seq_length": self.max_tokens,
            "query_prompt": QWEN_QUERY_PROMPT,
            "document_prompt": "",
            "pooling": "last_token",
            "padding_side": "left",
            "attention": "sdpa",
            "sentence_transformers": version("sentence-transformers"),
            "transformers": version("transformers"),
            "torch": version("torch"),
        }

    def encode(self, texts: list[str]) -> list[list[float]]:
        return _encode_prefixed(self.model, texts, "", self.max_tokens, self.batch_size)

    def encode_queries(self, texts: list[str]) -> list[list[float]]:
        return _encode_prefixed(
            self.model, texts, QWEN_QUERY_PROMPT, self.max_tokens, self.batch_size
        )


class E5Embedder:
    """Use the published multilingual E5 query/passage prefixes."""

    dimension = 1024

    def __init__(
        self,
        model_path: Path = Path("data/models/multilingual-e5-large"),
        *,
        device: str = "auto",
    ) -> None:
        verify_pinned_model_files(
            model_path,
            E5_MODEL_REVISION,
            (
                "model.safetensors",
                "config.json",
                "tokenizer.json",
                "tokenizer_config.json",
                "special_tokens_map.json",
                "sentencepiece.bpe.model",
                "sentence_bert_config.json",
                "modules.json",
                "1_Pooling/config.json",
            ),
            "Download E5 model files from the pinned revision",
        )

        import torch
        from sentence_transformers import SentenceTransformer

        self.device = resolve_device(device)
        torch.set_num_threads(4)
        self.model = SentenceTransformer(
            str(model_path),
            device=self.device,
            local_files_only=True,
            model_kwargs={"dtype": torch.float32, "attn_implementation": "sdpa"},
        )
        if self.model.max_seq_length != 512:
            raise ValueError("Expected the pinned E5 token limit of 512")

        self.max_tokens = 512
        self.batch_size = 2

    def count_tokens(self, text: str) -> int:
        return len(self.model.tokenizer.encode(text, add_special_tokens=False))

    def parameters(self) -> dict[str, object]:
        return {
            "model": E5_MODEL_ID,
            "revision": E5_MODEL_REVISION,
            "dimension": self.dimension,
            "normalize_embeddings": True,
            "device": self.device,
            "dtype": "float32",
            "batch_size": self.batch_size,
            "max_seq_length": self.max_tokens,
            "query_prompt": "query: ",
            "document_prompt": "passage: ",
            "pooling": "mean",
            "padding_side": self.model.tokenizer.padding_side,
            "attention": "sdpa",
            "sentence_transformers": version("sentence-transformers"),
            "transformers": version("transformers"),
            "torch": version("torch"),
        }

    def encode(self, texts: list[str]) -> list[list[float]]:
        return _encode_prefixed(
            self.model, texts, "passage: ", self.max_tokens, self.batch_size
        )

    def encode_queries(self, texts: list[str]) -> list[list[float]]:
        return _encode_prefixed(
            self.model, texts, "query: ", self.max_tokens, self.batch_size
        )


def _encode_prefixed(
    model: "SentenceTransformer",
    texts: list[str],
    prompt: str,
    max_tokens: int,
    batch_size: int,
) -> list[list[float]]:
    if not texts or any(not text.strip() for text in texts):
        raise ValueError("Embedding input must contain nonempty texts")

    prepared = [prompt + text for text in texts]
    tokens = model.tokenizer(prepared, padding=False, truncation=False)["input_ids"]

    if any(len(row) > max_tokens for row in tokens):
        raise ValueError("Embedding input including prompt exceeds model token limit")

    encoded = model.encode(
        prepared,
        prompt="",
        batch_size=batch_size,
        normalize_embeddings=True,
        show_progress_bar=len(texts) > batch_size,
        convert_to_numpy=True,
    )
    vectors: list[list[float]] = encoded.tolist()
    return vectors


def load_embedder(name: str, *, device: str = "auto") -> Embedder:
    if name == "bge-m3":
        return BGEEmbedder(device="cpu" if device == "auto" else device)
    if name == "qwen3-0.6b":
        return QwenEmbedder(device=device)
    if name == "multilingual-e5-large":
        return E5Embedder(device=device)
    raise ValueError(f"Unknown embedding model: {name}")
