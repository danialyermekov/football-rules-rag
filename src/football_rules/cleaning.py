"""Conservative cleanup with line-level provenance in the unchanged source text."""

import hashlib
import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import TypedDict

from football_rules.ingestion import PageRecord
from football_rules.jsonl import write_jsonl

RUNNING_HEADER = re.compile(
    r"^(?:\d+\s*)?(?:L\s*aws of the Game|Правила игры)\s+"
    r"20\d{2}\s*/\s*\d\s*\d\s*\|.+$"
)
NUMBERED_HEADING = re.compile(r"^\d{1,2}\.\s+\D")
TABLE_HEADING = re.compile(r"^(?:\d+\.\s*)?(?:Summary table|Сводная таблица)\b")
COMMON_HEADINGS = {
    "Procedure",
    "Процедура",
    "Offences and sanctions",
    "Нарушения и наказания",
}


class SourceSpan(TypedDict):
    start: int
    end: int


class CleanedBlock(TypedDict):
    kind: str
    text: str
    list_level: int | None
    source_spans: list[SourceSpan]


class RemovedSpan(TypedDict):
    start: int
    end: int
    reason: str


class CleanedPage(PageRecord):
    cleaned_text: str
    blocks: list[CleanedBlock]
    removed_spans: list[RemovedSpan]
    cleaning_flags: list[str]
    cleaning_version: str


@dataclass(frozen=True)
class SourceLine:
    text: str
    start: int
    end: int
    nested_bullet: bool


def source_lines(raw_text: str) -> list[SourceLine]:
    """Locate lines in the same whitespace-normalized text used by the dataset."""
    lines = []
    cursor = 0

    for raw_line in raw_text.splitlines():
        text = " ".join(raw_line.split())

        if text and cursor:
            cursor += 1

        start = cursor
        cursor += len(text)

        prefix = raw_line[: len(raw_line) - len(raw_line.lstrip())]
        nested_bullet = "\u2002" in prefix or len(prefix) >= 2

        lines.append(SourceLine(text, start, cursor, nested_bullet))

    return lines


def make_block(lines: list[SourceLine], kind: str) -> CleanedBlock:
    """Join wrapped lines; keep ordinary hyphens and all source line ranges."""
    text = lines[0].text

    for line in lines[1:]:
        if (
            kind != "unstructured"
            and text.endswith("\u00ad")
            and line.text[:1].isalpha()
        ):
            text = text[:-1] + line.text
        else:
            separator = "\n" if kind == "unstructured" else " "
            text += separator + line.text

    level = None

    if kind == "list_item":
        level = 1 if lines[0].nested_bullet else 0
        text = "  " * level + "• " + text[1:].lstrip()

    spans: list[SourceSpan] = []

    for line in lines:
        spans.append({"start": line.start, "end": line.end})

    return {"kind": kind, "text": text, "list_level": level, "source_spans": spans}


def clean_page(page: PageRecord) -> CleanedPage:
    """Create a separate cleaned view; retain every original page field."""
    if page["text"] != " ".join(page["raw_text"].split()):
        raise ValueError(
            f"{page['document_id']} page {page['pdf_page']}: source text is inconsistent"
        )

    lines = source_lines(page["raw_text"])
    nonempty = [index for index, line in enumerate(lines) if line.text]
    edges = {nonempty[0], nonempty[-1]} if nonempty else set()

    flags = []
    table_page = any(TABLE_HEADING.match(line.text) for line in lines)

    if table_page:
        flags.append("table_layout_not_reconstructed")

    if len(page["text"]) < 200:
        flags.append("sparse_text_review")

    if page["raster_image_count"]:
        flags.append("raster_images_not_interpreted")

    kept_lines = []
    removed: list[RemovedSpan] = []

    for index, line in enumerate(lines):
        reason = None

        if RUNNING_HEADER.fullmatch(line.text):
            reason = "running_header"
        elif index in edges and line.text == str(page["printed_page"]):
            reason = "printed_page_number"

        if reason is not None:
            removed.append({"start": line.start, "end": line.end, "reason": reason})
            kept_lines.append(SourceLine("", line.start, line.start, False))
        else:
            kept_lines.append(line)

    blocks: list[CleanedBlock] = []
    pending: list[SourceLine] = []
    kind = "text"

    for line in kept_lines:
        if not line.text:
            if pending:
                blocks.append(make_block(pending, kind))
                pending = []
            continue

        if pending and pending[-1].text.endswith("-") and line.text[:1].isalpha():
            flags.append("unresolved_line_hyphen")

        if table_page:
            pending.append(line)
            kind = "unstructured"
            continue

        bullet = line.text.startswith("•")
        heading = (
            bool(NUMBERED_HEADING.match(line.text)) or line.text in COMMON_HEADINGS
        )
        new_sentence = bool(pending) and pending[-1].text.endswith((".", "!", "?"))
        after_heading = (
            bool(pending)
            and kind == "heading"
            and (pending[0].text in COMMON_HEADINGS or line.text[:1].isupper())
        )
        # shortcut: paragraph boundaries are heuristic; use PDF geometry if retrieval needs finer structure.
        after_list = kind == "list_item" and line.text[:1].isupper()
        boundary = bullet or heading or new_sentence or after_heading or after_list

        if pending and boundary:
            blocks.append(make_block(pending, kind))
            pending = []

        if not pending:
            kind = "list_item" if bullet else "heading" if heading else "text"

        pending.append(line)

    if pending:
        blocks.append(make_block(pending, kind))

    cleaned: CleanedPage = {
        **page,
        "cleaned_text": "\n\n".join(block["text"] for block in blocks),
        "blocks": blocks,
        "removed_spans": removed,
        "cleaning_flags": sorted(set(flags)),
        "cleaning_version": "0.1.0",
    }

    return cleaned


def clean_corpus(input_path: Path, output_path: Path) -> dict[str, object]:
    """Clean the page artifact without overwriting it or losing partial results."""
    if input_path.resolve() == output_path.resolve():
        raise ValueError("Cleaned output must differ from the source artifact")

    content = input_path.read_bytes()
    pages = []
    identities = set()

    for line in content.decode("utf-8").splitlines():
        page = json.loads(line)
        identity = (page["document_id"], page["pdf_page"])

        if identity in identities:
            raise ValueError(f"Duplicate source page: {identity}")

        identities.add(identity)
        pages.append(clean_page(page))

    if not pages:
        raise ValueError("Source artifact contains no pages")

    output_hash = write_jsonl(output_path, pages)
    removed_counts = Counter(
        span["reason"] for page in pages for span in page["removed_spans"]
    )
    flag_counts = Counter(flag for page in pages for flag in page["cleaning_flags"])

    return {
        "input_sha256": hashlib.sha256(content).hexdigest(),
        "output": str(output_path),
        "sha256": output_hash,
        "pages": len(pages),
        "blocks": sum(len(page["blocks"]) for page in pages),
        "removed": dict(removed_counts),
        "flags": dict(flag_counts),
    }
