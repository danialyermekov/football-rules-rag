"""Deterministic checks for an experiment with removed source evidence."""

from typing import Any


def retain_context_pages(
    documents: list[dict[str, Any]],
    pages: list[int],
    required_pages: set[tuple[str, int]],
) -> list[dict[str, Any]]:
    """Keep audited remnants without changing their text, metadata or order."""
    selected = [document for document in documents if document["pdf_page"] in pages]
    if not selected or len(selected) == len(documents):
        raise ValueError("Ablation must keep a nonempty proper subset of context")
    if any(
        (document["document_id"], document["pdf_page"]) in required_pages
        for document in selected
    ):
        raise ValueError("Audited remainder still contains a required evidence page")
    return selected


def citation_integrity(output: dict[str, Any]) -> bool:
    """Empty citations are allowed for abstention; every supplied citation must exist."""
    citations = output["citations"]
    allowed = {
        f"{document['document_id']}:{document['pdf_page']}"
        for document in output["documents"]
    }
    return len(citations) == len(set(citations)) and set(citations).issubset(allowed)
