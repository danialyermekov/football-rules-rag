"""Context assembly within a deterministic token budget."""

from collections.abc import Callable
from typing import Any


def render_context(documents: list[dict[str, Any]]) -> str:
    """Format retrieved chunks with document and PDF page provenance headers."""
    parts = []
    for document in documents:
        label = (
            f"[{document['document_id']}; pdf_page={document['pdf_page']}; "
            f"printed_page={document['printed_page']}]"
        )
        parts.append(label + "\n" + document["text"])
    return "\n\n".join(parts)


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
