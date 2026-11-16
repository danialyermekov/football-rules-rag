"""Grounded answer generation subpackage."""

from football_rules.generation.gemini import (
    MODEL,
    SYSTEM_PROMPT,
    Answer,
    cited_documents,
    generate_answer,
    metric_value,
    valid_citations,
)

__all__ = [
    "MODEL",
    "SYSTEM_PROMPT",
    "Answer",
    "cited_documents",
    "generate_answer",
    "metric_value",
    "valid_citations",
]
