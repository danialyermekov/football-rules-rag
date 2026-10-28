"""Interactive and single-question CLI over E10 retrieval and grounded Gemini."""

from collections.abc import Callable
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import sys
from typing import Any, TextIO

from dotenv import load_dotenv
from google import genai
from google.genai import types

from football_rules.bm25 import BM25Retriever
from football_rules.embeddings import MODEL_REVISION, load_embedder
from football_rules.evidence_evaluation import pack_context
from football_rules.generation import generate_answer, valid_citations
from football_rules.hybrid import HybridRetriever
from football_rules.retrieval import DenseRetriever
from football_rules.tracking import configure_tracking

DEFAULT_COLLECTION = "football_44d75390ffa00dde1b74f0e6"
DEFAULT_SAVE_PATH = Path("tmp/saved-questions.jsonl")
SUPPORTED_LANGUAGES = ("ru", "en")
SUPPORTED_MODELS = (
    "gemini-2.5-flash-lite",
    "gemini-3.8-flash",
    "gemini-4-argon",
)


def generation_options(model: str) -> dict[str, Any]:
    if model not in SUPPORTED_MODELS:
        raise ValueError(f"Unsupported model: {model}")
    if model == "gemini-3.8-flash":
        return {"thinking_level": types.ThinkingLevel.LOW, "max_output_tokens": 2048}
    if model == "gemini-4-argon":
        return {
            "thinking_level": types.ThinkingLevel.LOW,
            "max_output_tokens": 32768,
            "temperature": None,
        }
    return {}


def _serialize_options(options: dict[str, Any]) -> dict[str, Any]:
    serialized: dict[str, Any] = {}
    for key, value in options.items():
        if isinstance(value, types.ThinkingLevel):
            serialized[key] = value.name
        else:
            serialized[key] = value
    return serialized


class AskSession:
    """Reusable E10 retrieval + Gemini generation session that loads models once."""

    def __init__(
        self,
        database: Path = Path("data/qdrant"),
        collection: str = DEFAULT_COLLECTION,
        chunks_path: Path = Path("data/processed/chunks.jsonl"),
    ) -> None:
        load_dotenv(".env")
        key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not key:
            raise ValueError("Configure GEMINI_API_KEY in environment or .env")
        self._api_key = key
        self.database = database
        self.collection = collection
        self.chunks_path = chunks_path

        from transformers import AutoTokenizer

        metadata = Path(
            "data/models/bge-m3/.cache/huggingface/download/tokenizer.json.metadata"
        )
        if metadata.read_text(encoding="utf-8").splitlines()[:1] != [MODEL_REVISION]:
            raise ValueError("Budget tokenizer differs from the pinned BGE revision")
        self.tokenizer = AutoTokenizer.from_pretrained(
            "data/models/bge-m3", revision=MODEL_REVISION, local_files_only=True
        )
        configure_tracking()
        self.lexical = BM25Retriever(chunks_path)
        self.dense = DenseRetriever(database, collection, load_embedder("qwen3-0.6b"))
        try:
            self.retriever = HybridRetriever(self.dense, self.lexical)
        except Exception:
            self.dense.close()
            raise
        self._closed = False

    def __enter__(self) -> "AskSession":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        if not self._closed:
            self._closed = True
            self.dense.close()

    def ask(
        self,
        query: str,
        language: str = "ru",
        model: str = "gemini-2.5-flash-lite",
    ) -> dict[str, Any]:
        if not query.strip() or language not in SUPPORTED_LANGUAGES:
            raise ValueError("Provide a nonempty question and language ru/en")
        options = generation_options(model)
        documents = self.retriever.search(query, language, 50)
        context = pack_context(
            documents,
            2048,
            lambda text: len(self.tokenizer.encode(text, add_special_tokens=False)),
        )
        with genai.Client(
            api_key=self._api_key,
            http_options=types.HttpOptions(
                timeout=900000 if model == "gemini-4-argon" else 60000,
                retry_options=types.HttpRetryOptions(attempts=1),
            ),
        ) as client:
            output = generate_answer(
                client, query, language, context["text"], model=model, **options
            )
        output["question"] = query
        output["language"] = language
        output["requested_model"] = model
        output["context"] = context["text"]
        output["context_token_count"] = context["token_count"]
        output["documents"] = context["documents"]
        output["settings"] = {
            "database": str(self.database),
            "collection": self.collection,
            "chunks_path": str(self.chunks_path),
            "embedding": "qwen3-0.6b",
            "strategy": "hybrid",
            "candidate_depth": 50,
            "token_budget": 2048,
            "generation_options": _serialize_options(options),
        }
        output["citations_valid"] = valid_citations(output)
        return output


def ask_question(
    query: str, language: str, model: str, database: Path, collection: str
) -> dict[str, Any]:
    if not query.strip() or language not in SUPPORTED_LANGUAGES:
        raise ValueError("Provide a nonempty question and language ru/en")
    with AskSession(database=database, collection=collection) as session:
        return session.ask(query, language, model)


def format_answer(report: dict[str, Any], default_model: str = "") -> str:
    lines = [
        report["answer"],
        "",
        f"Status: {report['status']}",
        f"Model: {report.get('model_version') or report.get('requested_model') or default_model}",
    ]
    if report["citations"]:
        lines.append("Sources (document:PDF page): " + ", ".join(report["citations"]))
    if not report["citations_valid"] and (
        report["citations"] or report["status"] == "answered"
    ):
        lines.append(
            "Citation check failed: the answer's references could not be validated."
        )
    return "\n".join(lines)


def format_sources(report: dict[str, Any]) -> str:
    documents = report.get("documents") or []
    if not documents:
        return "No context excerpts were packed for this answer."
    cited = set(report.get("citations") or [])
    blocks = []
    for index, doc in enumerate(documents, start=1):
        ref = f"{doc['document_id']}:{doc['pdf_page']}"
        printed = doc.get("printed_page", "?")
        chunk_id = doc.get("chunk_id", "?")
        marker = " [cited]" if ref in cited else ""
        header = f"[{index}] {ref} (printed_page={printed}, chunk_id={chunk_id}){marker}"
        blocks.append(f"{header}\n{doc['text']}")
    return "\n\n".join(blocks)


def save_report(
    report: dict[str, Any],
    path: Path = DEFAULT_SAVE_PATH,
    note: str | None = None,
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "saved_at": datetime.now(UTC).isoformat(),
        "question": report.get("question", ""),
        "language": report.get("language", ""),
        "requested_model": report.get("requested_model", ""),
        "model_version": report.get("model_version"),
        "status": report["status"],
        "answer": report["answer"],
        "citations": report["citations"],
        "citations_valid": report["citations_valid"],
        "generation_seconds": report.get("generation_seconds"),
        "usage": report.get("usage"),
        "settings": report.get("settings"),
        "context_token_count": report.get("context_token_count"),
        "context": report.get("context"),
        "documents": report["documents"],
    }
    if note and note.strip():
        record["note"] = note.strip()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


CHAT_HELP = """Available commands:
  /sources          Show the context excerpts used for the last answer
  /save [note]      Save the last question, sources, answer, and settings to JSONL
  /model [name]     Show or switch the active Gemini model
  /lang [ru|en]     Show or switch the question language
  /help             Show this help message
  /exit             Exit interactive chat"""


def chat_loop(
    session: AskSession,
    *,
    language: str = "ru",
    model: str = "gemini-2.5-flash-lite",
    save_path: Path = DEFAULT_SAVE_PATH,
    input_fn: Callable[[str], str] | None = None,
    output: TextIO | None = None,
) -> None:
    if language not in SUPPORTED_LANGUAGES:
        raise ValueError("Supported languages are ru and en")
    generation_options(model)
    reader = input if input_fn is None else input_fn
    stream = sys.stdout if output is None else output

    print(
        f"Ready (model={model}, language={language}, save={save_path}). "
        "Type a question or /help for commands.",
        file=stream,
    )
    last_report: dict[str, Any] | None = None

    while True:
        prompt = "\nВопрос: " if language == "ru" else "\nQuestion: "
        try:
            raw = reader(prompt)
        except (EOFError, KeyboardInterrupt):
            print(file=stream)
            break

        line = raw.strip()
        if not line:
            continue

        lower = line.lower()
        if lower in {"/exit", "/quit", ":q", "exit", "quit", "выход", "/выход"}:
            break

        if lower in {"/help", "/?", ":help", "/помощь"}:
            print(CHAT_HELP, file=stream)
            continue

        if lower in {"/sources", ":sources", "/источники"}:
            if last_report is None:
                print("No answer yet. Ask a question first.", file=stream)
            else:
                print(format_sources(last_report), file=stream)
            continue

        if (
            lower == "/save"
            or lower.startswith("/save ")
            or lower == ":save"
            or lower.startswith(":save ")
            or lower == "/сохранить"
            or lower.startswith("/сохранить ")
        ):
            if last_report is None:
                print("No answer to save yet. Ask a question first.", file=stream)
                continue
            parts = line.split(maxsplit=1)
            note = parts[1] if len(parts) > 1 else None
            save_report(last_report, save_path, note=note)
            print(f"Saved last answer to {save_path}", file=stream)
            continue

        if lower == "/model" or lower.startswith("/model "):
            parts = line.split(maxsplit=1)
            if len(parts) == 1:
                print(
                    f"Current model: {model} (choices: {', '.join(SUPPORTED_MODELS)})",
                    file=stream,
                )
            elif parts[1] in SUPPORTED_MODELS:
                model = parts[1]
                print(f"Model switched to {model}", file=stream)
            else:
                print(
                    f"Unknown model '{parts[1]}'. Choices: {', '.join(SUPPORTED_MODELS)}",
                    file=stream,
                )
            continue

        if (
            lower == "/lang"
            or lower.startswith("/lang ")
            or lower == "/language"
            or lower.startswith("/language ")
        ):
            parts = line.split(maxsplit=1)
            if len(parts) == 1:
                print(
                    f"Current language: {language} (choices: {', '.join(SUPPORTED_LANGUAGES)})",
                    file=stream,
                )
            elif parts[1] in SUPPORTED_LANGUAGES:
                language = parts[1]
                print(f"Language switched to {language}", file=stream)
            else:
                print(
                    f"Unknown language '{parts[1]}'. Choices: {', '.join(SUPPORTED_LANGUAGES)}",
                    file=stream,
                )
            continue

        if line.startswith("/"):
            print(
                f"Unknown command '{line.split()[0]}'. Type /help for commands.",
                file=stream,
            )
            continue

        try:
            last_report = session.ask(line, language, model)
        except Exception as exc:
            print(f"Error: {exc}", file=stream)
            continue

        header = "Ответ:" if language == "ru" else "Answer:"
        print(f"{header}\n{format_answer(last_report, model)}", file=stream)
