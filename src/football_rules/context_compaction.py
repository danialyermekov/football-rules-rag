"""Gold-blind context compaction with exact cleaned/source provenance."""

import hashlib
import json
from collections.abc import Callable
from typing import Any

from football_rules.chunking import source_positions, source_ranges
from football_rules.evidence_evaluation import Pages, render_context

PAGE_METADATA = (
    "document_id",
    "pdf_page",
    "printed_page",
    "edition",
    "language",
    "publisher",
    "source_url",
    "source_sha256",
    "cleaning_version",
    "cleaning_flags",
)


def _components(
    documents: list[dict[str, Any]],
) -> list[list[tuple[int, dict[str, Any]]]]:
    by_page: dict[tuple[str, int], list[tuple[int, dict[str, Any]]]] = {}
    for rank, document in enumerate(documents):
        key = document["document_id"], document["pdf_page"]
        by_page.setdefault(key, []).append((rank, document))
    groups = []
    for entries in by_page.values():
        current: list[tuple[int, dict[str, Any]]] = []
        right = -1
        for entry in sorted(
            entries, key=lambda item: (item[1]["cleaned_start"], item[0])
        ):
            start, end = entry[1]["cleaned_start"], entry[1]["cleaned_end"]
            if current and start >= right:
                groups.append(current)
                current = []
            current.append(entry)
            right = max(right, end) if len(current) > 1 else end
        if current:
            groups.append(current)
    return sorted(groups, key=lambda group: min(rank for rank, _ in group))


def _compact(
    selected: list[dict[str, Any]],
    pages: Pages,
    maps: dict[tuple[str, int], list[int | None]],
    original_ids: set[str],
) -> list[dict[str, Any]]:
    blocks = []
    for group in _components(selected):
        constituents = [
            document for _, document in sorted(group, key=lambda item: item[0])
        ]
        first = constituents[0]
        if len(constituents) == 1:
            blocks.append(first)
            continue
        start = min(d["cleaned_start"] for d in constituents)
        end = max(d["cleaned_end"] for d in constituents)
        key = first["document_id"], first["pdf_page"]
        page = pages[key]
        identities = [d["chunk_id"] for d in constituents]
        identity = (
            "overlap:"
            + hashlib.sha256(
                json.dumps(
                    [key, page["source_sha256"], start, end, identities],
                    ensure_ascii=False,
                ).encode("utf-8")
            ).hexdigest()
        )
        if identity in original_ids:
            raise ValueError("Synthetic context block collides with an original ID")
        blocks.append(
            {
                **{field: first[field] for field in PAGE_METADATA},
                "chunk_id": identity,
                "constituent_chunk_ids": identities,
                "cleaned_start": start,
                "cleaned_end": end,
                "text": page["cleaned_text"][start:end],
                "source_spans": source_ranges(maps[key][start:end], page["text"]),
            }
        )
    return blocks


def pack_overlap_context(
    documents: list[dict[str, Any]],
    pages: Pages,
    budget: int,
    count_tokens: Callable[[str], int],
) -> dict[str, Any]:
    """Greedily admit whole originals using their lossless overlap-compacted cost."""
    if budget <= 0:
        raise ValueError("Context token budget must be positive")
    original_ids = {document["chunk_id"] for document in documents}
    if len(original_ids) != len(documents):
        raise ValueError("Overlap packing requires unique candidate IDs")
    maps = {}
    for document in documents:
        key = document["document_id"], document["pdf_page"]
        if key not in pages:
            raise ValueError("Candidate source page is missing")
        page = pages[key]
        if key not in maps:
            maps[key] = source_positions(page)
        start, end = document["cleaned_start"], document["cleaned_end"]
        if not (
            type(start) is int
            and type(end) is int
            and 0 <= start < end <= len(page["cleaned_text"])
        ):
            raise ValueError("Invalid cleaned source interval")
        if document["text"] != page["cleaned_text"][start:end]:
            raise ValueError("Candidate text differs from its source interval")
        if any(
            field not in document or field not in page or document[field] != page[field]
            for field in PAGE_METADATA
        ):
            raise ValueError("Candidate source metadata differs from its page")
        if document["source_spans"] != source_ranges(
            maps[key][start:end], page["text"]
        ):
            raise ValueError("Candidate source spans differ from its source map")

    selected: list[dict[str, Any]] = []
    blocks = []
    skipped = []
    text = ""
    token_count = 0
    for document in documents:
        trial = [*selected, document]
        trial_blocks = _compact(trial, pages, maps, original_ids)
        trial_text = render_context(trial_blocks)
        trial_tokens = count_tokens(trial_text)
        if trial_tokens > budget:
            skipped.append({"chunk_id": document["chunk_id"], "reason": "token_budget"})
            continue
        selected = trial
        blocks = trial_blocks
        text = trial_text
        token_count = trial_tokens
    return {
        "documents": blocks,
        "selected_documents": selected,
        "text": text,
        "token_count": token_count,
        "skipped": skipped,
    }
