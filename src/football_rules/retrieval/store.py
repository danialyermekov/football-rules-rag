"""Persistent local Qdrant collections tied to corpus and embedding fingerprints."""

import hashlib
import json
import math
from importlib.metadata import version
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid5

import mlflow
from qdrant_client import QdrantClient, models

from football_rules.retrieval.embeddings import Embedder


def read_chunks(path: Path) -> list[dict[str, Any]]:
    chunks = [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
    ]

    if not chunks:
        raise ValueError("Chunk artifact is empty")

    identities = set()

    for chunk in chunks:
        identity = chunk["chunk_id"]

        if identity in identities or not chunk["text"].strip():
            raise ValueError("Chunks must have unique IDs and nonempty text")

        identities.add(identity)

    return chunks


def validate_vectors(vectors: list[list[float]], count: int, dimension: int) -> None:
    if len(vectors) != count:
        raise ValueError("Embedding count differs from text count")

    for vector in vectors:
        if len(vector) != dimension or not all(
            math.isfinite(value) for value in vector
        ):
            raise ValueError("Embedding has invalid dimension or nonfinite values")

        if not any(vector):
            raise ValueError("Embedding cannot be a zero vector")


def index_chunks(
    chunks_path: Path, database_path: Path, embedder: Embedder
) -> dict[str, object]:
    chunks = read_chunks(chunks_path)
    manifest: dict[str, Any] = {
        "chunks_sha256": hashlib.sha256(chunks_path.read_bytes()).hexdigest(),
        "embedding": embedder.parameters(),
        "distance": "Cosine",
        "qdrant_client": version("qdrant-client"),
        "points": len(chunks),
        "index_version": "0.1.0",
    }
    fingerprint = hashlib.sha256(
        json.dumps(manifest, sort_keys=True).encode()
    ).hexdigest()
    collection = "football_" + fingerprint[:24]
    manifest["collection"] = collection
    manifest_path = database_path / f"{collection}.json"
    database_path.mkdir(parents=True, exist_ok=True)
    client = QdrantClient(path=str(database_path))

    try:
        exists = client.collection_exists(collection)

        if exists and manifest_path.exists():
            if json.loads(manifest_path.read_text(encoding="utf-8")) != manifest:
                raise ValueError(
                    "Index manifest differs from the expected configuration"
                )
            if client.count(collection, exact=True).count != len(chunks):
                raise ValueError(
                    "Completed collection point count differs from manifest"
                )
            return {**manifest, "reused": True}

        vectors = embedder.encode([chunk["text"] for chunk in chunks])
        validate_vectors(vectors, len(chunks), embedder.dimension)

        if not exists:
            client.create_collection(
                collection,
                vectors_config=models.VectorParams(
                    size=embedder.dimension, distance=models.Distance.COSINE
                ),
            )

        points = [
            models.PointStruct(
                id=str(uuid5(NAMESPACE_URL, chunk["chunk_id"])),
                vector=vector,
                payload=chunk,
            )
            for chunk, vector in zip(chunks, vectors, strict=True)
        ]
        client.upsert(collection, points=points, wait=True)

        if client.count(collection, exact=True).count != len(chunks):
            raise ValueError("Qdrant point count differs from chunk count")

        # A manifest marks a completed index; interrupted upserts can be safely repeated.
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return {**manifest, "reused": False}
    finally:
        client.close()


def resolve_collection(
    database_path: Path,
    collection: str | None = None,
    embedding_model_id: str | None = None,
) -> str:
    """Resolve an explicit collection name or discover a compatible manifest on disk."""
    if collection is not None:
        return collection

    if not database_path.is_dir():
        raise ValueError(
            f"Qdrant database directory not found at {database_path}. Run `football-rules index` first."
        )

    matches: list[tuple[str, str]] = []
    for manifest_path in sorted(database_path.glob("football_*.json")):
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        model = manifest.get("embedding", {}).get("model")
        name = manifest.get("collection") or manifest_path.stem
        if embedding_model_id is None or model == embedding_model_id:
            matches.append((name, str(model or "")))

    if not matches:
        hint = f" for embedding '{embedding_model_id}'" if embedding_model_id else ""
        raise ValueError(
            f"No Qdrant collection manifest found in {database_path}{hint}. Run `football-rules index` first."
        )
    return matches[-1][0]


RUNTIME_EMBEDDING_KEYS = {
    "device",
    "batch_size",
    "torch",
    "transformers",
    "sentence_transformers",
    "attention",
}


def _embedding_signature(parameters: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in parameters.items() if k not in RUNTIME_EMBEDDING_KEYS}


class DenseRetriever:
    def __init__(
        self, database_path: Path, collection: str, embedder: Embedder
    ) -> None:
        self.manifest = json.loads(
            (database_path / f"{collection}.json").read_text(encoding="utf-8")
        )

        if _embedding_signature(self.manifest["embedding"]) != _embedding_signature(
            embedder.parameters()
        ):
            raise ValueError(
                "Query embedder differs from the indexed embedding configuration"
            )

        self.embedder = embedder
        self.collection = collection
        self.client = QdrantClient(path=str(database_path))

        if self.client.count(collection, exact=True).count != self.manifest["points"]:
            self.client.close()
            raise ValueError("Index is incomplete")

    def close(self) -> None:
        self.client.close()

    @mlflow.trace(span_type="RETRIEVER")
    def search(self, query: str, language: str, k: int = 5) -> list[dict[str, Any]]:
        if not query.strip() or language not in {"en", "ru"} or k <= 0:
            raise ValueError("Provide a nonempty query, language en/ru and positive k")

        with mlflow.start_span(name="query_embedding", span_type="EMBEDDING") as span:
            span.set_inputs({"texts": [query]})
            vectors = self.embedder.encode_queries([query])
            validate_vectors(vectors, 1, self.embedder.dimension)
            vector = vectors[0]
            span.set_outputs({"vector": vector})
        hits = self.client.query_points(
            self.collection,
            query=vector,
            query_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="language", match=models.MatchValue(value=language)
                    )
                ]
            ),
            limit=k,
            with_payload=True,
        ).points

        return [{"score": hit.score, **(hit.payload or {})} for hit in hits]
