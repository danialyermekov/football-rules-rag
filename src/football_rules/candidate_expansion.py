"""Combine cached and fresh scores of the same reranker without rank fusion."""

import math
from typing import Any

from football_rules.reranking import rank_documents

Document = dict[str, Any]


def _validate_scored(raw: list[Document], scored: list[Document]) -> None:
    by_id = {document["chunk_id"]: document for document in scored}
    if len(by_id) != len(scored) or set(by_id) != {d["chunk_id"] for d in raw}:
        raise ValueError("Scored records must cover exactly the original candidates")
    scores = [by_id[document["chunk_id"]]["score"] for document in raw]
    if rank_documents(raw, scores) != scored:
        raise ValueError("Scored records changed provenance, score order or tie-break")


def tail_candidates(
    fused: list[Document], cached_prefix: list[Document]
) -> list[Document]:
    """Return the raw suffix only after validating the cached scored prefix."""
    if len({d["chunk_id"] for d in fused}) != len(fused):
        raise ValueError("Fused candidates must have unique IDs")
    if not cached_prefix or len(cached_prefix) > len(fused):
        raise ValueError("A nonempty scored prefix of the fused pool is required")
    if not all(math.isfinite(d["score"]) for d in fused):
        raise ValueError("Original retrieval scores must be finite")
    boundary = len(cached_prefix)
    _validate_scored(fused[:boundary], cached_prefix)
    return fused[boundary:]


def merge_reranked_candidates(
    fused: list[Document],
    cached_prefix: list[Document],
    fresh_tail: list[Document],
) -> list[Document]:
    """Return one common score ranking, preserving every raw candidate's provenance."""
    tail = tail_candidates(fused, cached_prefix)
    _validate_scored(tail, fresh_tail)
    scores = {d["chunk_id"]: d["score"] for d in [*cached_prefix, *fresh_tail]}
    return rank_documents(fused, [scores[d["chunk_id"]] for d in fused])
