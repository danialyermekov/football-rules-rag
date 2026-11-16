"""Deterministic chunk relevance labels and standard binary ranking metrics."""

import math
from typing import Any


def ranking_metrics(
    retrieved: list[str], relevant: list[str], k: int
) -> dict[str, float]:
    if k <= 0 or len(retrieved) != len(set(retrieved)):
        raise ValueError("Metrics require positive k and unique retrieved IDs")

    if not relevant:
        return {"recall": 0.0, "precision": 0.0, "mrr": 0.0, "ndcg": 0.0}

    gold = set(relevant)
    gains = [int(identity in gold) for identity in retrieved[:k]]
    hits = sum(gains)
    reciprocal = next((1 / rank for rank, gain in enumerate(gains, 1) if gain), 0.0)
    dcg = sum(gain / math.log2(rank + 1) for rank, gain in enumerate(gains, 1))
    ideal = sum(1 / math.log2(rank + 1) for rank in range(1, min(k, len(gold)) + 1))

    return {
        "recall": hits / len(gold),
        "precision": hits / k,
        "mrr": reciprocal,
        "ndcg": dcg / ideal,
    }


def relevant_chunks(
    chunks: list[dict[str, Any]],
    locators: list[dict[str, Any]],
    pages: dict[tuple[str, int], dict[str, Any]],
    threshold: float = 0.8,
) -> list[str]:
    """A chunk is relevant if it covers >=80% of any required evidence locator."""
    if not 0 < threshold <= 1 or not locators:
        raise ValueError("Relevance requires evidence and a threshold in (0, 1]")

    relevant = set()

    for locator in locators:
        identity = (locator["document_id"], locator["pdf_page"])
        page = pages[identity]
        removed = {
            index
            for span in page["removed_spans"]
            for index in range(span["start"], span["end"])
        }
        evidence = {
            index
            for index in range(locator["char_start"], locator["char_end"])
            if not page["text"][index].isspace() and index not in removed
        }

        if not evidence:
            raise ValueError("Evidence locator has no retained substantive text")

        for chunk in chunks:
            if (chunk["document_id"], chunk["pdf_page"]) != identity:
                continue

            covered = {
                index
                for span in chunk["source_spans"]
                for index in range(span["start"], span["end"])
                if not page["text"][index].isspace()
            }

            if len(evidence & covered) / len(evidence) >= threshold:
                relevant.add(chunk["chunk_id"])

    return sorted(relevant)
