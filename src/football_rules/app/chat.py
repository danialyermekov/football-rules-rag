"""Interactive terminal chat loop over an open AskSession."""

import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TextIO

from football_rules.app.formatter import format_answer, format_sources, save_report
from football_rules.app.service import AskSession, generation_options
from football_rules.config import (
    DEFAULT_SAVE_PATH,
    SUPPORTED_LANGUAGES,
    SUPPORTED_MODELS,
)

CHAT_HELP = """Available commands:
  /sources          Show the context excerpts used for the last answer
  /save [note]      Save the last question, sources, answer, and settings to JSONL
  /model [name]     Show or switch the active Gemini model
  /lang [ru|en]     Show or switch the question language
  /help             Show this help message
  /exit             Exit interactive chat"""


@dataclass
class _ChatState:
    language: str
    model: str
    save_path: Path
    last_report: dict[str, Any] | None = None


def _switch_option(
    line: str,
    current: str,
    choices: tuple[str, ...],
    label: str,
    stream: TextIO,
) -> str:
    parts = line.split(maxsplit=1)

    if len(parts) == 1:
        print(f"Current {label}: {current} (choices: {', '.join(choices)})", file=stream)
        return current

    value = parts[1]
    if value in choices:
        print(f"{label.capitalize()} switched to {value}", file=stream)
        return value

    print(f"Unknown {label} '{value}'. Choices: {', '.join(choices)}", file=stream)
    return current


def _handle_command(line: str, state: _ChatState, stream: TextIO) -> bool:
    """Handle one interactive slash command. Return False to exit the loop."""
    lower = line.lower()

    if lower in {"/exit", "/quit", ":q", "exit", "quit", "выход", "/выход"}:
        return False

    if lower in {"/help", "/?", ":help", "/помощь"}:
        print(CHAT_HELP, file=stream)
        return True

    if lower in {"/sources", ":sources", "/источники"}:
        if state.last_report is None:
            print("No answer yet. Ask a question first.", file=stream)
        else:
            print(format_sources(state.last_report), file=stream)
        return True

    if lower in {"/save", ":save", "/сохранить"} or lower.startswith(
        ("/save ", ":save ", "/сохранить ")
    ):
        if state.last_report is None:
            print("No answer to save yet. Ask a question first.", file=stream)
            return True

        parts = line.split(maxsplit=1)
        note = parts[1] if len(parts) > 1 else None
        save_report(state.last_report, state.save_path, note=note)
        print(f"Saved last answer to {state.save_path}", file=stream)
        return True

    if lower == "/model" or lower.startswith("/model "):
        state.model = _switch_option(
            line, state.model, SUPPORTED_MODELS, "model", stream
        )
        return True

    if lower in {"/lang", "/language"} or lower.startswith(("/lang ", "/language ")):
        state.language = _switch_option(
            line, state.language, SUPPORTED_LANGUAGES, "language", stream
        )
        return True

    print(
        f"Unknown command '{line.split()[0]}'. Type /help for commands.",
        file=stream,
    )
    return True


def _is_command(line: str) -> bool:
    lower = line.lower()
    return line.startswith("/") or lower in {
        ":q",
        ":help",
        ":sources",
        ":save",
        "exit",
        "quit",
        "выход",
    } or lower.startswith(":save ")


def chat_loop(
    session: AskSession,
    *,
    language: str = "ru",
    model: str = "gemini-2.5-flash-lite",
    save_path: Path = DEFAULT_SAVE_PATH,
    input_fn: Callable[[str], str] | None = None,
    output: TextIO | None = None,
) -> None:
    """Run an interactive question-answering loop against an open AskSession."""
    if language not in SUPPORTED_LANGUAGES:
        raise ValueError("Supported languages are ru and en")

    generation_options(model)

    reader = input if input_fn is None else input_fn
    stream = sys.stdout if output is None else output
    state = _ChatState(language=language, model=model, save_path=save_path)

    print(
        f"Ready (model={model}, language={language}, save={save_path}). "
        "Type a question or /help for commands.",
        file=stream,
    )

    while True:
        prompt = "\nВопрос: " if state.language == "ru" else "\nQuestion: "

        try:
            raw = reader(prompt)
        except (EOFError, KeyboardInterrupt):
            print(file=stream)
            break

        line = raw.strip()
        if not line:
            continue

        if _is_command(line):
            if not _handle_command(line, state, stream):
                break
            continue

        try:
            state.last_report = session.ask(line, state.language, state.model)
        except Exception as exc:  # noqa: BLE001 - keep interactive chat alive on transient errors
            print(f"Error: {exc}", file=stream)
            continue

        header = "Ответ:" if state.language == "ru" else "Answer:"
        print(f"{header}\n{format_answer(state.last_report, state.model)}", file=stream)
