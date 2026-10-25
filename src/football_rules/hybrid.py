"""Equal-weight RRF over dense and lexical retrievers."""

from typing import Any

import mlflow

from football_rules.bm25 import BM25Retriever
from football_rules.retrieval import DenseRetriever
from football_rules.sparse_retrieval import BGESparseRetriever


def reciprocal_rank_fusion(
    dense: list[dict[str, Any]],
    bm25: list[dict[str, Any]],
    *,
    lexical_name: str = "bm25",
) -> list[dict[str, Any]]:
    if lexical_name not in {"bm25", "bge_m3_sparse"}:
        raise ValueError("Unknown lexical branch")
    combined: dict[str, dict[str, Any]] = {}

    for name, documents in (("dense", dense), (lexical_name, bm25)):
        seen = set()

        for rank, document in enumerate(documents, start=1):
            identity = document["chunk_id"]

            if identity in seen:
                raise ValueError("Each RRF input must contain unique chunk IDs")

            seen.add(identity)

            if identity not in combined:
                combined[identity] = {
                    **document,
                    "score": 0.0,
                    "branch_ranks": {},
                    "branch_scores": {},
                }

            hit = combined[identity]
            hit["score"] += 1 / (60 + rank)
            hit["branch_ranks"][name] = rank
            hit["branch_scores"][name] = document["score"]

    return sorted(combined.values(), key=lambda hit: (-hit["score"], hit["chunk_id"]))


class HybridRetriever:
    """Own the dense client and return the complete fused union for diagnostics."""

    def __init__(
        self, dense: DenseRetriever, bm25: BM25Retriever | BGESparseRetriever
    ) -> None:
        if dense.manifest["chunks_sha256"] != bm25.manifest["chunks_sha256"]:
            dense.close()
            raise ValueError("Hybrid branches must use the same chunk corpus")

        self.dense = dense
        self.bm25 = bm25
        self.lexical_name = bm25.manifest["strategy"]
        self.manifest = {
            **dense.manifest,
            "strategy": "hybrid",
            self.lexical_name: bm25.manifest,
            "fusion": {
                "method": "RRF",
                "rank_constant": 60,
                "rank_origin": 1,
                "weights": "equal",
                "deduplication": "chunk_id",
                "tie_break": "chunk_id_ascending",
            },
        }

    def close(self) -> None:
        self.dense.close()

    @mlflow.trace(name="hybrid_search", span_type="RETRIEVER")
    def search(
        self, query: str, language: str, branch_depth: int = 50
    ) -> list[dict[str, Any]]:
        dense_hits = self.dense.search(query, language, branch_depth)
        bm25_hits = self.bm25.search(query, language, branch_depth)

        with mlflow.start_span(
            name="reciprocal_rank_fusion", span_type="CHAIN"
        ) as span:
            span.set_inputs(
                {
                    "dense_ids": [hit["chunk_id"] for hit in dense_hits],
                    f"{self.lexical_name}_ids": [hit["chunk_id"] for hit in bm25_hits],
                    "rank_constant": 60,
                }
            )
            fused = reciprocal_rank_fusion(
                dense_hits, bm25_hits, lexical_name=self.lexical_name
            )
            span.set_outputs(fused)

        return fused
