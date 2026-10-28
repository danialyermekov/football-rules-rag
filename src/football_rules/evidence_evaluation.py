"""Chunk-independent evidence coverage and deterministic context packing."""

from collections.abc import Callable
from itertools import pairwise
from typing import Any

PageKey = tuple[str, int]
Pages = dict[PageKey, dict[str, Any]]


def retained_positions(page: dict[str, Any], start: int, end: int) -> set[int]:
    if not 0 <= start < end <= len(page["text"]):
        raise ValueError("Source range is outside the page")

    removed = {
        index
        for span in page["removed_spans"]
        for index in range(span["start"], span["end"])
    }
    return {
        index
        for index in range(start, end)
        if not page["text"][index].isspace() and index not in removed
    }


def evidence_metrics(
    documents: list[dict[str, Any]],
    required: list[dict[str, Any]],
    pages: Pages,
    threshold: float = 0.8,
) -> dict[str, float]:
    """Every locator of every required unit must pass the completeness threshold."""
    if not required or not 0 < threshold <= 1:
        raise ValueError("Evidence metrics require gold units and threshold in (0, 1]")

    covered: dict[PageKey, set[int]] = {}
    total_positions = 0

    for document in documents:
        key = (document["document_id"], document["pdf_page"])
        page = pages[key]
        positions = set()

        for span in document["source_spans"]:
            positions.update(retained_positions(page, span["start"], span["end"]))

        total_positions += len(positions)
        covered.setdefault(key, set()).update(positions)

    unit_coverage = []
    complete = []
    strict = []

    for unit in required:
        if not unit["locators"]:
            raise ValueError("Evidence unit has no locators")

        locator_coverage = []

        for locator in unit["locators"]:
            key = (locator["document_id"], locator["pdf_page"])
            gold = retained_positions(
                pages[key], locator["char_start"], locator["char_end"]
            )

            if not gold:
                raise ValueError("Evidence locator contains no retained text")

            fraction = len(gold & covered.get(key, set())) / len(gold)
            locator_coverage.append(fraction)

        unit_coverage.append(sum(locator_coverage) / len(locator_coverage))
        complete.append(all(value >= threshold for value in locator_coverage))
        strict.append(all(value == 1.0 for value in locator_coverage))

    unique_positions = sum(len(positions) for positions in covered.values())
    return {
        "evidence_coverage": sum(unit_coverage) / len(unit_coverage),
        "evidence_recall": sum(complete) / len(complete),
        "complete_evidence": float(all(complete)),
        "strict_complete_evidence": float(all(strict)),
        "source_redundancy": (
            1 - unique_positions / total_positions if total_positions else 0.0
        ),
    }


def render_context(documents: list[dict[str, Any]]) -> str:
    parts = []

    for document in documents:
        label = (
            f"[{document['document_id']}; pdf_page={document['pdf_page']}; "
            f"printed_page={document['printed_page']}]"
        )
        parts.append(label + "\n" + document["text"])

    return "\n\n".join(parts)


def chunk_successors(
    chunks: list[dict[str, Any]], *, cross_page_only: bool = False
) -> dict[str, str]:
    """Link adjacent chunks; crossing a page requires a bullet-list continuation."""
    if len({chunk["chunk_id"] for chunk in chunks}) != len(chunks):
        raise ValueError("Successor mapping requires unique chunk IDs")

    ordered = sorted(
        chunks,
        key=lambda chunk: (
            chunk["document_id"],
            chunk["pdf_page"],
            chunk["cleaned_start"],
            chunk["chunk_id"],
        ),
    )
    successors = {}

    for current, following in pairwise(ordered):
        if any(
            current.get(key) != following.get(key)
            for key in ("document_id", "language", "edition")
        ):
            continue

        same_page = current["pdf_page"] == following["pdf_page"]
        next_page_list = following["pdf_page"] == current["pdf_page"] + 1 and following[
            "text"
        ].lstrip().startswith("•")
        if (same_page and not cross_page_only) or next_page_list:
            successors[current["chunk_id"]] = following["chunk_id"]

    return successors


def prioritize_successors(
    documents: list[dict[str, Any]], successors: dict[str, str]
) -> list[dict[str, Any]]:
    """Promote at most one retrieved successor per anchor, without adding candidates."""
    by_id = {document["chunk_id"]: document for document in documents}
    if len(by_id) != len(documents):
        raise ValueError("Successor ordering requires unique candidate IDs")

    ordered = []
    seen = set()
    for document in documents:
        identity = document["chunk_id"]
        if identity in seen:
            continue

        for candidate in (identity, successors.get(identity)):
            if candidate is None or candidate not in by_id or candidate in seen:
                continue
            ordered.append(by_id[candidate])
            seen.add(candidate)

    return ordered


def prioritize_rule_neighbors(
    documents: list[dict[str, Any]], successors: dict[str, str]
) -> list[dict[str, Any]]:
    """Visit one retrieved predecessor, anchor, successor per ranked anchor."""
    by_id = {document["chunk_id"]: document for document in documents}
    if len(by_id) != len(documents):
        raise ValueError("Neighbor ordering requires unique candidate IDs")
    predecessors = {following: previous for previous, following in successors.items()}
    if len(predecessors) != len(successors):
        raise ValueError("Each chunk must have at most one predecessor")
    ordered = []
    seen = set()
    for document in documents:
        identity = document["chunk_id"]
        if identity in seen:
            continue
        for candidate in (
            predecessors.get(identity),
            identity,
            successors.get(identity),
        ):
            if candidate in by_id and candidate not in seen:
                ordered.append(by_id[candidate])
                seen.add(candidate)
    return ordered


def pack_context(
    documents: list[dict[str, Any]],
    budget: int,
    count_tokens: Callable[[str], int],
) -> dict[str, Any]:
    """Pack whole chunks in rank order; skip over-budget chunks and exact duplicates."""
    if budget <= 0:
        raise ValueError("Context token budget must be positive")

    selected: list[dict[str, Any]] = []
    skipped = []
    seen = set()
    token_count = 0
    text = ""

    for document in documents:
        identity = document["chunk_id"]

        if identity in seen:
            skipped.append({"chunk_id": identity, "reason": "duplicate_id"})
            continue

        seen.add(identity)
        candidate_text = render_context([*selected, document])
        candidate_tokens = count_tokens(candidate_text)

        if candidate_tokens > budget:
            skipped.append({"chunk_id": identity, "reason": "token_budget"})
            continue

        selected.append(document)
        text = candidate_text
        token_count = candidate_tokens

    return {
        "documents": selected,
        "text": text,
        "token_count": token_count,
        "skipped": skipped,
    }
