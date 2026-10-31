"""Scenario-scoped sensitivity metric: OR of complete evidence witness sets."""

from typing import Any

from football_rules.evidence_evaluation import Pages, evidence_metrics


def alternative_evidence_metrics(
    documents: list[dict[str, Any]],
    required: list[dict[str, Any]],
    alternatives: list[list[dict[str, Any]]],
    pages: Pages,
) -> dict[str, float]:
    # Materialise every result: short-circuiting would skip invalid later options.
    results = [
        evidence_metrics(documents, option, pages)
        for option in [required, *alternatives]
    ]
    return {
        f"{prefix}_{metric}": (
            results[0][metric]
            if prefix == "canonical"
            else float(any(result[metric] for result in results))
        )
        for prefix in ("canonical", "alternative")
        for metric in ("complete_evidence", "strict_complete_evidence")
    }
