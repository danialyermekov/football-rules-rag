"""User-facing CLI and interactive question-answering session."""

from football_rules.app.chat import (
    AskSession,
    ask_question,
    chat_loop,
    format_answer,
    format_sources,
    generation_options,
    save_report,
)

__all__ = [
    "AskSession",
    "ask_question",
    "chat_loop",
    "format_answer",
    "format_sources",
    "generation_options",
    "save_report",
]
