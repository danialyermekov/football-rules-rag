"""Freeze two predeclared, scenario-specific candidates and blinded source packets."""

import hashlib
import json
from pathlib import Path


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load(path):
    return [
        json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines()
    ]


def main():
    scenarios = {s["id"]: s for s in load("data/evaluation/scenarios.jsonl")}
    evidence = {e["id"]: e for e in load("data/evaluation/evidence.jsonl")}
    pages = {
        (p["document_id"], p["pdf_page"]): p
        for p in load("data/processed/cleaned-pages.jsonl")
    }
    candidates, packets = [], []
    specs = [
        (
            "FR005",
            "ru",
            12,
            "меры, предусматривающей",
            "8 секунд",
            "Introduction does not explicitly name the corner recipient; assess ordinary inference and source authority. Scenario supplies own penalty area.",
        ),
        (
            "FR050",
            "en",
            182,
            "Law 14",
            "if the ball enters the goal from the kick, the kick is retaken",
            "Heading must establish Law 14 rather than shoot-out Law 10. Do not generalise to deliberate second touch.",
        ),
    ]
    for identity, language, number, start_phrase, end_phrase, limitation in specs:
        scenario = scenarios[identity]
        document = f"ifab-2026-27-{language}"
        page = pages[document, number]
        text = page["text"]
        assert text.count(start_phrase) == text.count(end_phrase) == 1
        start = text.index(start_phrase)
        end = text.index(end_phrase) + len(end_phrase)
        locator = dict(
            document_id=document,
            pdf_page=number,
            printed_page=page["printed_page"],
            char_start=start,
            char_end=end,
            span_sha256=sha(text[start:end]),
        )
        required = [{"id": f"q3_{identity}_{language}", "locators": [locator]}]
        candidates.append(
            dict(
                scenario_id=identity,
                language=language,
                approved=False,
                review_status="pending_two_assistant_reviews_not_expert_reviewed",
                required_evidence=required,
                limitation=limitation,
            )
        )
        canonical = []
        for unit in scenario["required_evidence"]:
            for loc in evidence[unit]["locators"][language]:
                source = pages[loc["document_id"], loc["pdf_page"]]["text"]
                canonical.append(
                    dict(
                        unit=unit,
                        locator=loc,
                        text=source[loc["char_start"] : loc["char_end"]],
                    )
                )
        packets.append(
            dict(
                scenario_id=identity,
                language=language,
                question=scenario["questions"][language],
                reference=scenario["reference_answers"][language],
                must_include=scenario["must_include"][language],
                must_not_claim=scenario["must_not_claim"][language],
                canonical=canonical,
                candidate_locator=locator,
                candidate_span=text[start:end],
                candidate_page=text,
                limitation=limitation,
            )
        )
    manifest = dict(
        schema_version=1,
        status="candidate_not_expert_reviewed",
        source_hashes={
            p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
            for p in [
                "data/evaluation/scenarios.jsonl",
                "data/evaluation/evidence.jsonl",
                "data/processed/cleaned-pages.jsonl",
            ]
        },
        candidates=candidates,
    )
    for path, value in [
        ("data/evaluation/evidence-alternatives-q3.json", manifest),
        ("docs/evaluation-q3-review-packet.json", packets),
    ]:
        Path(path).write_text(
            json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )


if __name__ == "__main__":
    main()
