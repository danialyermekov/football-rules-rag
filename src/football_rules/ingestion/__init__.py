"""Document ingestion, cleaning, and chunking subpackage."""

from football_rules.ingestion.chunking import (
    ChunkConfig,
    ChunkRecord,
    chunk_corpus,
    chunk_page,
)
from football_rules.ingestion.cleaning import (
    CleanedPage,
    SourceSpan,
    clean_corpus,
    clean_page,
)
from football_rules.ingestion.pdf import (
    PageRecord,
    SourceDocument,
    extract_document,
    ingest,
    load_sources,
)

__all__ = [
    "ChunkConfig",
    "ChunkRecord",
    "CleanedPage",
    "PageRecord",
    "SourceDocument",
    "SourceSpan",
    "chunk_corpus",
    "chunk_page",
    "clean_corpus",
    "clean_page",
    "extract_document",
    "ingest",
    "load_sources",
]
