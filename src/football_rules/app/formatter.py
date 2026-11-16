"""Presentation formatting and JSONL report persistence."""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from football_rules.config import DEFAULT_SAVE_PATH


def format_answer(report: dict[str, Any], default_model: str = "") -> str:
    """Format an answer report for terminal display."""
    model_name = (
        report.get("model_version") or report.get("requested_model") or default_model
    )
    lines = [
        report["answer"],
        "",
        f"Status: {report['status']}",
        f"Model: {model_name}",
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
    """Format packed context excerpts, marking cited pages."""
    documents = report.get("documents") or []

    if not documents:
        return "No context excerpts were packed for this answer."

    cited = set(report.get("citations") or [])
    blocks: list[str] = []

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
    """Append a question/answer report record to a JSONL file."""
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
