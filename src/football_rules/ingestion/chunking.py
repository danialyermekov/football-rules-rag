"""Recursive text chunks with exact character provenance in the source page."""

import hashlib
import json
from collections import Counter
from dataclasses import asdict, dataclass
from importlib.metadata import version
from pathlib import Path
from typing import TypedDict

from langchain_text_splitters import RecursiveCharacterTextSplitter

from football_rules.ingestion.cleaning import CleanedPage, SourceSpan
from football_rules.io import write_jsonl

SEPARATORS = ["\n\n", "\n", ". ", "! ", "? ", " ", ""]


@dataclass(frozen=True)
class ChunkConfig:
    chunk_size: int = 1000
    chunk_overlap: int = 150

    def __post_init__(self) -> None:
        if self.chunk_size <= 0:
            raise ValueError("chunk_size must be positive")

        if not 0 <= self.chunk_overlap < self.chunk_size:
            raise ValueError("chunk_overlap must satisfy 0 <= overlap < chunk_size")

    def parameters(self) -> dict[str, object]:
        return {
            **asdict(self),
            "strategy": "recursive_character",
            "length_unit": "unicode_characters",
            "separators": SEPARATORS,
            "keep_separator": "end",
            "page_boundary": "never_cross",
            "splitter_version": version("langchain-text-splitters"),
            "chunking_version": "0.1.0",
        }


class ChunkRecord(TypedDict):
    chunk_id: str
    document_id: str
    edition: str
    language: str
    publisher: str
    source_url: str
    source_sha256: str
    pdf_page: int
    printed_page: int | None
    text: str
    cleaned_start: int
    cleaned_end: int
    source_spans: list[SourceSpan]
    cleaning_version: str
    cleaning_flags: list[str]
    chunking: dict[str, object]


def source_positions(page: CleanedPage) -> list[int | None]:
    """Map nonwhitespace cleaned characters to the unchanged source `text`."""
    expected = "\n\n".join(block["text"] for block in page["blocks"])

    if expected != page["cleaned_text"]:
        raise ValueError("cleaned_text does not match the page blocks")

    positions: list[int | None] = []
    previous_end = 0

    for block_index, block in enumerate(page["blocks"]):
        if block_index:
            positions.extend([None, None])

        original_positions: list[int] = []

        for span in block["source_spans"]:
            start, end = span["start"], span["end"]

            if not previous_end <= start < end <= len(page["text"]):
                raise ValueError("Source ranges must be ordered and within the page")

            previous_end = end
            original_positions.extend(
                index
                for index in range(start, end)
                if not page["text"][index].isspace()
            )

        cursor = 0

        for character in block["text"]:
            if character.isspace():
                positions.append(None)
                continue

            # Cleaning can remove an explicit soft hyphen when joining two lines.
            if cursor < len(original_positions):
                original = page["text"][original_positions[cursor]]

                if original == "\u00ad" and character != "\u00ad":
                    cursor += 1

            if cursor == len(original_positions):
                raise ValueError("Cleaned block has characters absent from its source")

            position = original_positions[cursor]

            if page["text"][position] != character:
                raise ValueError("Cleaned block differs from its source ranges")

            positions.append(position)
            cursor += 1

        if cursor != len(original_positions):
            raise ValueError("Source ranges contain text absent from the cleaned block")

    return positions


def source_ranges(positions: list[int | None], source_text: str) -> list[SourceSpan]:
    """Compact character positions without bridging removed nonwhitespace text."""
    spans: list[SourceSpan] = []

    for position in positions:
        if position is None:
            continue

        if spans and (
            position == spans[-1]["end"]
            or source_text[spans[-1]["end"] : position].isspace()
        ):
            spans[-1]["end"] = position + 1
        else:
            spans.append({"start": position, "end": position + 1})

    return spans


def chunk_page(page: CleanedPage, config: ChunkConfig) -> list[ChunkRecord]:
    positions = source_positions(page)
    parameters = config.parameters()
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=config.chunk_size,
        chunk_overlap=config.chunk_overlap,
        separators=SEPARATORS,
        keep_separator="end",
        add_start_index=True,
    )
    chunks: list[ChunkRecord] = []
    covered = bytearray(len(page["cleaned_text"]))

    for document in splitter.create_documents([page["cleaned_text"]]):
        text = document.page_content
        start = document.metadata["start_index"]
        end = start + len(text)

        if start < 0 or page["cleaned_text"][start:end] != text:
            raise ValueError("Splitter returned an invalid cleaned-text range")

        if not text.strip() or len(text) > config.chunk_size:
            raise ValueError("Splitter returned an empty or oversized chunk")

        covered[start:end] = b"\x01" * len(text)
        spans = source_ranges(positions[start:end], page["text"])

        identity = {
            "document_id": page["document_id"],
            "source_sha256": page["source_sha256"],
            "pdf_page": page["pdf_page"],
            "cleaning_version": page["cleaning_version"],
            "chunking": parameters,
            "start": start,
            "end": end,
            "text": text,
        }
        chunk_id = hashlib.sha256(
            json.dumps(identity, sort_keys=True, ensure_ascii=False).encode("utf-8")
        ).hexdigest()

        chunks.append(
            {
                "chunk_id": chunk_id,
                "document_id": page["document_id"],
                "edition": page["edition"],
                "language": page["language"],
                "publisher": page["publisher"],
                "source_url": page["source_url"],
                "source_sha256": page["source_sha256"],
                "pdf_page": page["pdf_page"],
                "printed_page": page["printed_page"],
                "text": text,
                "cleaned_start": start,
                "cleaned_end": end,
                "source_spans": spans,
                "cleaning_version": page["cleaning_version"],
                "cleaning_flags": page["cleaning_flags"],
                "chunking": parameters,
            }
        )

    if any(
        not covered[index]
        for index, position in enumerate(positions)
        if position is not None
    ):
        raise ValueError("Splitter omitted nonwhitespace text from the page")

    return chunks


def chunk_corpus(
    input_path: Path, output_path: Path, config: ChunkConfig
) -> dict[str, object]:
    """Build the chunk artifact; return reproducible configuration and statistics."""
    if input_path.resolve() == output_path.resolve():
        raise ValueError("Chunk output must differ from the source artifact")

    content = input_path.read_bytes()
    pages = [json.loads(line) for line in content.decode("utf-8").splitlines()]

    if not pages:
        raise ValueError("Source artifact contains no pages")

    chunks = []
    identities = set()

    for page in pages:
        identity = (page["document_id"], page["pdf_page"])

        if identity in identities:
            raise ValueError(f"Duplicate source page: {identity}")

        identities.add(identity)
        chunks.extend(chunk_page(page, config))

    if not chunks:
        raise ValueError("Source artifact contains no chunkable text")

    lengths = sorted(len(chunk["text"]) for chunk in chunks)
    output_hash = write_jsonl(output_path, chunks)

    return {
        "input_sha256": hashlib.sha256(content).hexdigest(),
        "output": str(output_path),
        "sha256": output_hash,
        "config": config.parameters(),
        "pages": len(pages),
        "empty_pages": sum(not page["cleaned_text"] for page in pages),
        "chunks": len(chunks),
        "chunks_by_language": dict(Counter(chunk["language"] for chunk in chunks)),
        "characters": {
            "min": lengths[0],
            "median": lengths[len(lengths) // 2],
            "max": lengths[-1],
        },
    }
