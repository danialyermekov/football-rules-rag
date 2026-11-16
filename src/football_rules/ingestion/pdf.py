"""Page-level PDF extraction preserving the evaluation dataset's text coordinates."""

import hashlib
import json
import re
from collections import Counter
from dataclasses import dataclass
from importlib.metadata import version
from io import BytesIO
from pathlib import Path
from typing import TypedDict

from pypdf import PageObject, PdfReader, mult
from pypdf.generic import DictionaryObject

from football_rules.io import write_jsonl


@dataclass(frozen=True)
class SourceDocument:
    id: str
    edition: str
    language: str
    publisher: str
    source_url: str
    local_path: str
    sha256: str
    bytes: int
    pdf_pages: int


class PageRecord(TypedDict):
    document_id: str
    edition: str
    language: str
    publisher: str
    source_url: str
    source_sha256: str
    pdf_page: int
    printed_page: int | None
    printed_page_method: str
    raw_text: str
    text: str
    raster_image_count: int
    flags: list[str]
    extractor: dict[str, str]


def load_sources(manifest_path: Path) -> list[SourceDocument]:
    """Read the existing source manifest; reject incomplete or ambiguous entries."""
    entries = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(entries, list) or not entries:
        raise ValueError("Source manifest must be a non-empty list")

    sources = []

    for entry in entries:
        if not isinstance(entry, dict):
            raise TypeError("Each source entry must be an object")

        for field in (
            "id",
            "edition",
            "language",
            "publisher",
            "source_url",
            "local_path",
            "sha256",
        ):
            if not isinstance(entry.get(field), str) or not entry[field].strip():
                raise ValueError(f"Source entry requires a non-empty string: {field}")

        if not re.fullmatch(r"[0-9a-f]{64}", entry["sha256"]):
            raise ValueError(f"{entry['id']}: invalid SHA-256")

        for field in ("bytes", "pdf_pages"):
            if type(entry.get(field)) is not int or entry[field] <= 0:
                raise ValueError(f"{entry['id']}: {field} must be a positive integer")

        source = SourceDocument(
            id=entry["id"],
            edition=entry["edition"],
            language=entry["language"],
            publisher=entry["publisher"],
            source_url=entry["source_url"],
            local_path=entry["local_path"],
            sha256=entry["sha256"],
            bytes=entry["bytes"],
            pdf_pages=entry["pdf_pages"],
        )
        sources.append(source)

    if len({source.id for source in sources}) != len(sources):
        raise ValueError("Source manifest contains duplicate document IDs")

    return sources


def source_path(source: SourceDocument, root: Path) -> Path:
    """Resolve the manifest's repository-relative PDF path within the source root."""
    path = (root / source.local_path).resolve()

    if Path(source.local_path).is_absolute() or not path.is_relative_to(root.resolve()):
        raise ValueError(f"{source.id}: PDF path must stay within the source root")

    return path


def _extract_page(
    source: SourceDocument, page: PageObject, number: int, extractor: dict[str, str]
) -> PageRecord:
    footer_numbers: set[int] = set()

    def visit_text(
        text: str,
        cm: list[float],
        tm: list[float],
        font: DictionaryObject | None,
        font_size: float,
    ) -> None:
        label = text.strip()
        if label.isascii() and label.isdecimal():
            matrix = mult(tm, cm)
            x = matrix[4] - float(page.mediabox.left)
            y = matrix[5] - float(page.mediabox.bottom)
            width = float(page.mediabox.width)
            # shortcut: IFAB numbers sit in bottom outer corners; recalibrate for new layouts.
            at_edge = 0 <= x <= width * 0.2 or width * 0.8 <= x <= width
            if (
                at_edge
                and 0 <= y <= float(page.mediabox.height) * 0.07
                and int(label) > 0
            ):
                footer_numbers.add(int(label))

    raw_text = page.extract_text(visitor_text=visit_text) or ""
    text = " ".join(raw_text.split())

    flags = []

    if not text:
        flags.append("no_text")
    elif len(text) < 100:
        flags.append("short_text")

    printed_page = next(iter(footer_numbers)) if len(footer_numbers) == 1 else None

    if not footer_numbers:
        flags.append("printed_page_not_found")
    elif len(footer_numbers) > 1:
        flags.append("printed_page_ambiguous")

    return {
        "document_id": source.id,
        "edition": source.edition,
        "language": source.language,
        "publisher": source.publisher,
        "source_url": source.source_url,
        "source_sha256": source.sha256,
        "pdf_page": number,
        "printed_page": printed_page,
        "printed_page_method": (
            "footer_heuristic" if printed_page is not None else "not_determined"
        ),
        "raw_text": raw_text,
        "text": text,
        "raster_image_count": len(page.images.keys()),
        "flags": flags,
        "extractor": extractor,
    }


def extract_document(source: SourceDocument, root: Path) -> list[PageRecord]:
    """Extract every page of a hash-verified PDF, including empty/image pages."""
    path = source_path(source, root)
    content = path.read_bytes()

    if (
        len(content) != source.bytes
        or hashlib.sha256(content).hexdigest() != source.sha256
    ):
        raise ValueError(
            f"{source.id}: PDF size or SHA-256 does not match the manifest"
        )
    if not content.startswith(b"%PDF"):
        raise ValueError(f"{source.id}: file is not a PDF")

    extractor = {
        "name": "pypdf",
        "version": version("pypdf"),
        "fonttools_version": version("fonttools"),
    }
    records: list[PageRecord] = []

    with BytesIO(content) as stream:
        reader = PdfReader(stream)

        if reader.is_encrypted:
            raise ValueError(f"{source.id}: encrypted PDFs are not supported")
        if len(reader.pages) != source.pdf_pages:
            raise ValueError(f"{source.id}: PDF page count does not match the manifest")

        for number, page in enumerate(reader.pages, 1):
            records.append(_extract_page(source, page, number, extractor))

    return records


def ingest(manifest_path: Path, output_path: Path, root: Path) -> dict[str, object]:
    """Extract the registered sources and replace the output only after success."""
    sources = load_sources(manifest_path)

    input_paths = {manifest_path.resolve()}

    for source in sources:
        input_paths.add(source_path(source, root))

    if output_path.resolve() in input_paths:
        raise ValueError("Output must not overwrite the source manifest or a PDF")

    records: list[PageRecord] = []

    for source in sources:
        records.extend(extract_document(source, root))

    output_hash = write_jsonl(output_path, records)

    documents = []

    for source in sources:
        pages = [page for page in records if page["document_id"] == source.id]
        documents.append(
            {
                "document_id": source.id,
                "pdf_pages": len(pages),
                "flags": dict(
                    Counter(flag for page in pages for flag in page["flags"])
                ),
                "pages_with_raster_images": sum(
                    page["raster_image_count"] > 0 for page in pages
                ),
            }
        )

    return {
        "output": str(output_path),
        "sha256": output_hash,
        "documents": documents,
    }
