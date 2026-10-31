import copy
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from analyze_q2_metric_gates import analyze


class MetricGateAnalysisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path(__file__).resolve().parents[1] / "docs/evaluation-q1-review.json"
        cls.data = json.loads(path.read_text(encoding="utf-8"))

    def test_duplicate_reviews_and_unresolved_cases_are_not_counted(self):
        result = analyze(self.data)
        self.assertEqual(result["included"], 45)
        self.assertEqual(set(result["exclusions"]), {"Q017", "Q020", "Q047"})
        gates = result["evaluation"]["random"]["faithfulness"]["0.8"]
        self.assertEqual(gates["counts"], {"TP": 1, "FP": 7, "FN": 2, "TN": 12})
        self.assertEqual(set(gates["cases"]["FN"]), {"Q019", "Q031"})

    def test_threshold_is_inclusive_for_high_score(self):
        data = copy.deepcopy(self.data)
        row = next(r for r in data["selection"]["records"] if r["audit_id"] == "Q001")
        row["scores"]["faithfulness"] = 0.8
        equal = analyze(data)["evaluation"]["targeted"]["faithfulness"]["0.8"]
        self.assertIn("Q001", equal["cases"]["TN"])
        row["scores"]["faithfulness"] = 0.799
        below = analyze(data)["evaluation"]["targeted"]["faithfulness"]["0.8"]
        self.assertIn("Q001", below["cases"]["FP"])

    def test_refuses_non_boolean_critical_label(self):
        data = copy.deepcopy(self.data)
        review = next(
            r
            for r in data["phase_a_all"]
            if r["audit_id"] == "Q001" and r["reviewer"] == 1
        )
        review["critical_error"] = None
        with self.assertRaisesRegex(ValueError, "critical_error must be boolean"):
            analyze(data)


if __name__ == "__main__":
    unittest.main()
