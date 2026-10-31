"""Analyze Q1's saved scores against assistant reviews; no judge calls."""

import argparse
import json
from collections import Counter
from pathlib import Path

EXCLUSIONS = {
    "Q017": "reviewers disagreed on critical_error",
    "Q020": "decision_correct is unresolved for refusal",
    "Q047": "decision_correct is unresolved for refusal",
}


def analyze(data):
    selection = data["selection"]["records"]
    reviews = data["phase_a_all"]
    if len(selection) != 48 or len({row["audit_id"] for row in selection}) != 48:
        raise ValueError("Expected 48 unique Q1 selected snapshots")
    primary = {}
    for review in reviews:
        number = int(review["audit_id"][1:])
        if review["reviewer"] == (number - 1) // 16 + 1:
            if review["audit_id"] in primary:
                raise ValueError("Duplicate primary review")
            primary[review["audit_id"]] = review
    if set(primary) != {row["audit_id"] for row in selection}:
        raise ValueError("Missing primary review")
    for aid in ("Q020", "Q047"):
        if primary[aid]["decision_correct"] is not None:
            raise ValueError("Refusal exclusion no longer matches Q1")
    disagreements = {
        review["critical_error"] for review in reviews if review["audit_id"] == "Q017"
    }
    if disagreements != {True, False}:
        raise ValueError("Q017 disagreement no longer matches Q1")
    rows = [row for row in selection if row["audit_id"] not in EXCLUSIONS]
    result = {
        "population": len(selection),
        "included": len(rows),
        "exclusions": EXCLUSIONS,
        "unique_scenarios": len({row["scenario_id"] for row in rows}),
        "evaluation": {},
    }
    for stratum in ("random", "targeted", "all"):
        group = [row for row in rows if stratum == "all" or row["stratum"] == stratum]
        result["evaluation"][stratum] = {}
        for metric in ("faithfulness", "factual_correctness"):
            result["evaluation"][stratum][metric] = {}
            for threshold in (0.8, 1.0):
                cases = {name: [] for name in ("TP", "FP", "FN", "TN")}
                for row in group:
                    review = primary[row["audit_id"]]
                    bad = review["critical_error"]
                    if type(bad) is not bool:
                        raise ValueError("critical_error must be boolean")
                    flagged = row["scores"][metric] < threshold
                    key = ("T" if flagged == bad else "F") + ("P" if flagged else "N")
                    cases[key].append(row["audit_id"])
                counts = {name: len(ids) for name, ids in cases.items()}
                positives = counts["TP"] + counts["FN"]
                negatives = counts["TN"] + counts["FP"]
                result["evaluation"][stratum][metric][str(threshold)] = {
                    "n": len(group),
                    "counts": counts,
                    "sensitivity": counts["TP"] / positives if positives else None,
                    "specificity": counts["TN"] / negatives if negatives else None,
                    "cases": cases,
                }
    assert Counter(row["stratum"] for row in rows) == {"random": 22, "targeted": 23}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    source = Path("docs/evaluation-q1-review.json")
    result = analyze(json.loads(source.read_text(encoding="utf-8")))
    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        with args.output.open("x", encoding="utf-8", newline="\n") as file:
            file.write(text)
    print(text, end="")


if __name__ == "__main__":
    main()
