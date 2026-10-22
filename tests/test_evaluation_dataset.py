import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from validate_dataset import read_jsonl, validate, validate_sources


class DatasetValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scenarios = read_jsonl(ROOT / "data/evaluation/scenarios.jsonl")
        cls.evidence = read_jsonl(ROOT / "data/evaluation/evidence.jsonl")
        cls.sources = json.loads((ROOT / "docs/source-manifest.json").read_text(encoding="utf-8"))

    def test_dataset_is_consistent(self):
        validate(self.scenarios, self.evidence, self.sources)

    def test_original_splits_are_preserved(self):
        original_test_ids = {f"FR{n:03}" for n in (13, 16, 21, 24, 27, 29, 30, 36, 38, 43, 47, 49, 54, 58, 59)}
        original_rows = [row for row in self.scenarios if int(row["id"][2:]) <= 60]
        self.assertEqual(len(original_rows), 60)
        self.assertEqual({row["id"] for row in original_rows if row["split"] == "test"}, original_test_ids)

    def test_missing_translation_is_rejected(self):
        rows = copy.deepcopy(self.scenarios)
        del rows[0]["questions"]["ru"]
        with self.assertRaisesRegex(AssertionError, "questions languages"):
            validate(rows, self.evidence, self.sources)

    def test_wrong_split_sizes_are_rejected(self):
        rows = copy.deepcopy(self.scenarios)
        row = next(r for r in rows if r["id"] == "FR016")
        row["split"] = "dev"
        with self.assertRaisesRegex(AssertionError, "75 dev / 25 test"):
            validate(rows, self.evidence, self.sources)

    def test_unknown_evidence_is_rejected(self):
        rows = copy.deepcopy(self.scenarios)
        rows[0]["required_evidence"] = ["nonexistent_passage"]
        with self.assertRaisesRegex(AssertionError, "unknown evidence"):
            validate(rows, self.evidence, self.sources)

    def test_related_scenarios_cannot_leak_between_splits(self):
        rows = copy.deepcopy(self.scenarios)
        related = [r for r in rows if r["scenario_group"] == "restart_direct_goal"]
        related[1]["split"] = "test"
        with self.assertRaisesRegex(AssertionError, "different splits"):
            validate(rows, self.evidence, self.sources)

    @unittest.skipUnless((ROOT / "data/processed/reference-pages.json").exists(), "Local source snapshot absent")
    def test_changed_evidence_text_is_rejected(self):
        evidence = copy.deepcopy(self.evidence)
        evidence[0]["locators"]["en"][0]["char_start"] += 1
        manifest = json.loads((ROOT / "data/evaluation/manifest.json").read_text(encoding="utf-8"))
        with self.assertRaisesRegex(AssertionError, "ball_out"):
            validate_sources(evidence, self.sources, manifest)


if __name__ == "__main__":
    unittest.main()
