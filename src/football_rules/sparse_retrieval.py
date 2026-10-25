"""BGE-M3 learned lexical weights and exact sparse search for the small corpus."""

import hashlib
import json
import math
from importlib.metadata import version
from pathlib import Path
from typing import Any

import mlflow

from football_rules.embeddings import MODEL_ID, MODEL_REVISION
from football_rules.retrieval import read_chunks


def lexical_weights(
    token_ids: list[int], weights: list[float], excluded: set[int]
) -> dict[str, float]:
    """Match BGE-M3: positive weights, max over repeated tokens, no special tokens."""
    if len(token_ids) != len(weights) or any(not math.isfinite(w) for w in weights):
        raise ValueError("Sparse weights must be finite and aligned with tokens")
    result: dict[str, float] = {}
    for token, weight in zip(token_ids, weights, strict=True):
        if token not in excluded and weight > 0:
            key = str(token)
            result[key] = max(result.get(key, 0.0), weight)
    return result


class BGESparseRetriever:
    def __init__(
        self,
        chunks_path: Path,
        model_path: Path = Path("data/models/bge-m3"),
        cache_directory: Path = Path("data/sparse"),
    ) -> None:
        for name in (
            "pytorch_model.bin",
            "config.json",
            "tokenizer.json",
            "tokenizer_config.json",
            "special_tokens_map.json",
            "sparse_linear.pt",
        ):
            metadata = model_path / ".cache/huggingface/download" / f"{name}.metadata"
            if (
                not (model_path / name).is_file()
                or not metadata.is_file()
                or metadata.read_text(encoding="utf-8").splitlines()[:1]
                != [MODEL_REVISION]
            ):
                raise ValueError("Download the pinned BGE-M3 encoder and sparse head")

        import torch
        from transformers import AutoModel, AutoTokenizer

        if not torch.cuda.is_available():
            raise ValueError("Sparse experiment requires CUDA; use --extra cuda")
        torch.set_num_threads(4)
        self.max_tokens = 1024
        self.batch_size = 2
        self.tokenizer = AutoTokenizer.from_pretrained(
            str(model_path), local_files_only=True
        )
        self.model = (
            AutoModel.from_pretrained(
                str(model_path),
                local_files_only=True,
                dtype=torch.float32,
                attn_implementation="sdpa",
            )
            .to("cuda")
            .eval()
        )
        self.head = torch.nn.Linear(self.model.config.hidden_size, 1)
        self.head.load_state_dict(
            torch.load(
                model_path / "sparse_linear.pt", map_location="cpu", weights_only=True
            )
        )
        self.head = self.head.to("cuda").eval()
        self.excluded = {
            self.tokenizer.cls_token_id,
            self.tokenizer.eos_token_id,
            self.tokenizer.pad_token_id,
            self.tokenizer.unk_token_id,
        }
        self.documents = read_chunks(chunks_path)
        if any(d["language"] not in {"ru", "en"} for d in self.documents):
            raise ValueError("Sparse corpus languages must be en/ru")
        self.manifest: dict[str, Any] = {
            "strategy": "bge_m3_sparse",
            "version": "bge_m3_relu_max_dot_v1",
            "model": MODEL_ID,
            "revision": MODEL_REVISION,
            "chunks_sha256": hashlib.sha256(chunks_path.read_bytes()).hexdigest(),
            "points": len(self.documents),
            "device": "cuda",
            "dtype": "float32",
            "batch_size": self.batch_size,
            "max_tokens": self.max_tokens,
            "truncation": "reject_overflow",
            "instruction": "none",
            "normalization": "none",
            "scoring": "dot_product",
            "special_tokens": "exclude_cls_eos_pad_unk",
            "repeated_tokens": "max",
            "zero_score_hits": "excluded",
            "tie_break": "chunk_id_ascending",
            "torch": version("torch"),
            "transformers": version("transformers"),
            "attention": "sdpa",
        }
        fingerprint = hashlib.sha256(
            json.dumps(self.manifest, sort_keys=True).encode()
        ).hexdigest()
        self.index_path = cache_directory / f"{fingerprint}.json"
        if self.index_path.exists():
            saved = json.loads(self.index_path.read_text(encoding="utf-8"))
            if saved["manifest"] != self.manifest:
                raise ValueError("Sparse cache manifest mismatch")
            self.vectors = saved["vectors"]
            if len(self.vectors) != len(self.documents) or any(
                not isinstance(token, str)
                or not token.isdecimal()
                or not math.isfinite(weight)
                or weight <= 0
                for vector in self.vectors
                for token, weight in vector.items()
            ):
                raise ValueError("Invalid sparse cache vectors")
        else:
            self.vectors = self.encode([d["text"] for d in self.documents])
            cache_directory.mkdir(parents=True, exist_ok=True)
            temporary = self.index_path.with_suffix(".tmp")
            temporary.write_text(
                json.dumps({"manifest": self.manifest, "vectors": self.vectors}),
                encoding="utf-8",
            )
            temporary.replace(self.index_path)
        self.manifest["index_sha256"] = hashlib.sha256(
            self.index_path.read_bytes()
        ).hexdigest()

    def encode(self, texts: list[str]) -> list[dict[str, float]]:
        import torch

        if not texts or any(not text.strip() for text in texts):
            raise ValueError("Sparse encoding requires nonempty texts")
        result: list[dict[str, float]] = []
        with torch.inference_mode():
            for start in range(0, len(texts), self.batch_size):
                inputs = self.tokenizer(
                    texts[start : start + self.batch_size],
                    padding=True,
                    truncation=False,
                    return_tensors="pt",
                )
                if inputs["input_ids"].shape[1] > self.max_tokens:
                    raise ValueError("Sparse input exceeds token limit")
                hidden = self.model(**inputs.to("cuda")).last_hidden_state
                weights = torch.relu(self.head(hidden)).squeeze(-1).cpu().tolist()
                ids = inputs["input_ids"].cpu().tolist()
                result.extend(
                    lexical_weights(tokens, values, self.excluded)
                    for tokens, values in zip(ids, weights, strict=True)
                )
        return result

    @mlflow.trace(name="bge_m3_sparse_search", span_type="RETRIEVER")
    def search(self, query: str, language: str, k: int = 5) -> list[dict[str, Any]]:
        if not query.strip() or language not in {"ru", "en"} or k <= 0:
            raise ValueError("Provide a nonempty query, language en/ru and positive k")
        query_weights = self.encode([query])[0]
        hits = []
        for document, weights in zip(self.documents, self.vectors, strict=True):
            if document["language"] != language:
                continue
            score = sum(
                weight * weights.get(token, 0.0)
                for token, weight in query_weights.items()
            )
            if score > 0:
                hits.append({**document, "score": score})
        return sorted(hits, key=lambda hit: (-hit["score"], hit["chunk_id"]))[:k]
