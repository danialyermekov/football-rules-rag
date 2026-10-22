"""Validate the evaluation artifact; --check-sources also checks local source files."""

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LANGUAGES = {"ru", "en"}
TYPES = {"answerable", "insufficient_information", "conditional_answer", "out_of_scope"}


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def validate(scenarios: list[dict], evidence: list[dict], sources: list[dict]) -> None:
    source_map = {source["id"]: source for source in sources}
    evidence_map = {item["id"]: item for item in evidence}
    assert len(source_map) == len(sources), "Duplicate source ID"
    assert len(evidence_map) == len(evidence), "Duplicate evidence ID"
    assert len(scenarios) == 100, "Expected 100 scenarios"
    assert {row["id"] for row in scenarios} == {f"FR{i:03}" for i in range(1, 101)}, "Scenario IDs"
    questions = {lang: set() for lang in LANGUAGES}
    groups = {}
    used_evidence = set()
    covered_laws = set()
    for row in scenarios:
        label = row["id"]
        assert row["edition"] == "2026/27", label
        assert row["question_type"] in TYPES, label
        assert row["split"] in {"dev", "test", "unassigned"}, label
        assert row["review_status"] == "agent_source_checked_not_expert_reviewed", label
        assert row["provenance"]["paid_api_used"] is False, label
        assert groups.setdefault(row["scenario_group"], row["split"]) == row["split"], (
            f"Related scenarios span different splits: {row['scenario_group']}"
        )
        for field in ("questions", "reference_answers", "must_include", "must_not_claim"):
            assert set(row[field]) == LANGUAGES, f"{label}: {field} languages"
            for lang, value in row[field].items():
                if field in {"must_include", "must_not_claim"}:
                    assert isinstance(value, list) and value, f"{label}: {field}"
                    assert all(isinstance(v, str) and v.strip() for v in value), label
                else:
                    assert isinstance(value, str) and value.strip(), f"{label}: {field}"
        for lang in LANGUAGES:
            question = " ".join(row["questions"][lang].casefold().split())
            assert question not in questions[lang], f"{label}: duplicate {lang} question"
            questions[lang].add(question)
        required = row["required_evidence"]
        assert len(required) == len(set(required)), f"{label}: repeated evidence"
        if row["question_type"] == "out_of_scope":
            assert not required, f"{label}: unsupported question cannot have answer evidence"
        else:
            assert required, f"{label}: missing required evidence"
        for key in required + row["related_evidence"]:
            assert key in evidence_map, f"{label}: unknown evidence {key}"
            used_evidence.add(key)
        covered_laws.update(int(evidence_map[key]["section"].split(".")[0]) for key in required)
    assert covered_laws == set(range(1, 18)), "Not all 17 Laws covered"
    assert Counter(row["split"] for row in scenarios) == {"dev": 75, "test": 25}, "Expected 75 dev / 25 test scenarios"
    assert used_evidence == set(evidence_map), "Unused evidence"
    for item in evidence:
        assert set(item["locators"]) == LANGUAGES, item["id"]
        for lang, spans in item["locators"].items():
            assert spans, item["id"]
            for span in spans:
                source = source_map[span["document_id"]]
                assert source["language"] == lang, item["id"]
                assert 1 <= span["pdf_page"] <= source["pdf_pages"], item["id"]
                assert 0 < span["printed_page"], item["id"]
                assert 0 <= span["char_start"] < span["char_end"], item["id"]
                assert len(span["span_sha256"]) == 64, item["id"]


def validate_sources(evidence: list[dict], sources: list[dict], manifest: dict) -> None:
    snapshot = ROOT / manifest["source_snapshot"]["local_path"]
    content = snapshot.read_bytes()
    assert hashlib.sha256(content).hexdigest() == manifest["source_snapshot"]["sha256"], "Snapshot hash"
    pages = json.loads(content)
    for source in sources:
        content = (ROOT / source["local_path"]).read_bytes()
        assert content.startswith(b"%PDF"), source["id"]
        assert len(content) == source["bytes"], source["id"]
        assert hashlib.sha256(content).hexdigest() == source["sha256"], source["id"]
        assert len(pages[source["language"]]) == source["pdf_pages"], source["id"]
    for item in evidence:
        for lang, spans in item["locators"].items():
            for span in spans:
                page = pages[lang][span["pdf_page"] - 1]
                assert span["char_end"] <= len(page), item["id"]
                passage = page[span["char_start"]:span["char_end"]]
                assert hashlib.sha256(passage.encode("utf-8")).hexdigest() == span["span_sha256"], item["id"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-sources", action="store_true")
    args = parser.parse_args()
    folder = ROOT / "data/evaluation"
    scenarios = read_jsonl(folder / "scenarios.jsonl")
    evidence = read_jsonl(folder / "evidence.jsonl")
    sources = json.loads((ROOT / "docs/source-manifest.json").read_text(encoding="utf-8"))
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    validate(scenarios, evidence, sources)
    assert manifest["scenario_count"] == len(scenarios)
    assert manifest["question_count"] == sum(len(row["questions"]) for row in scenarios)
    assert manifest["evidence_count"] == len(evidence)
    assert manifest["split_counts"] == dict(Counter(row["split"] for row in scenarios))
    for name, expected_hash in manifest["artifact_sha256"].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == expected_hash, name
    if args.check_sources:
        validate_sources(evidence, sources, manifest)
    question_count = sum(len(row["questions"]) for row in scenarios)
    print(f"PASS: {len(scenarios)} scenarios, {question_count} questions, {len(evidence)} evidence units, all 17 Laws")
    print("Types:", dict(Counter(row["question_type"] for row in scenarios)))
    print("Splits:", dict(Counter(row["split"] for row in scenarios)))
    print("Source hashes/spans checked" if args.check_sources else "Local PDF files and source spans not checked")


if __name__ == "__main__":
    main()
