"""Central configuration defaults for the Football Rules RAG pipeline."""

from pathlib import Path

DEFAULT_MANIFEST_PATH = Path("docs/source-manifest.json")
DEFAULT_PAGES_PATH = Path("data/processed/pages.jsonl")
DEFAULT_CLEANED_PAGES_PATH = Path("data/processed/cleaned-pages.jsonl")
DEFAULT_CHUNKS_PATH = Path("data/processed/chunks.jsonl")
DEFAULT_QDRANT_PATH = Path("data/qdrant")
DEFAULT_MODELS_DIR = Path("data/models")
DEFAULT_SAVE_PATH = Path("tmp/saved-questions.jsonl")

DEFAULT_CHUNK_SIZE = 1000
DEFAULT_CHUNK_OVERLAP = 150

DEFAULT_INDEX_EMBEDDING = "bge-m3"
DEFAULT_ASK_EMBEDDING = "qwen3-0.6b"
DEFAULT_COLLECTION = "football_44d75390ffa00dde1b74f0e6"
DEFAULT_BRANCH_DEPTH = 50
DEFAULT_CONTEXT_BUDGET = 2048

SUPPORTED_LANGUAGES = ("ru", "en")
DEFAULT_LANGUAGE = "ru"

DEFAULT_GENERATION_MODEL = "gemini-2.5-flash-lite"
SUPPORTED_MODELS = (
    "gemini-2.5-flash-lite",
    "gemini-3.8-flash",
    "gemini-4-argon",
)
