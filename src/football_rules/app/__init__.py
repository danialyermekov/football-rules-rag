"""Application layer: QA orchestration, formatting, and interactive chat."""

from football_rules.app.chat import CHAT_HELP, chat_loop
from football_rules.app.formatter import format_answer, format_sources, save_report
from football_rules.app.service import AskSession, ask_question, generation_options

__all__ = [
    "CHAT_HELP",
    "AskSession",
    "ask_question",
    "chat_loop",
    "format_answer",
    "format_sources",
    "generation_options",
    "save_report",
]
