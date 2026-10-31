import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from evaluate_e22_budget_oracle import search_oracle, validate_runtime_environment


class BudgetOracleTests(unittest.TestCase):
    def setUp(self):
        self.pages = {
            ("a", 1): {"text": "abcdefghij", "removed_spans": []},
            ("a", 2): {"text": "abcdefghij", "removed_spans": []},
        }
        self.gold = [
            {
                "id": "x",
                "locators": [
                    {"document_id": "a", "pdf_page": 1, "char_start": 0, "char_end": 10}
                ],
            }
        ]

    def doc(self, identity, page, start, end):
        return {
            "chunk_id": identity,
            "document_id": "a",
            "pdf_page": page,
            "printed_page": page,
            "text": "text",
            "source_spans": [{"start": start, "end": end}],
        }

    def test_missing_telemetry_workaround_fails_before_evaluation(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ValueError, "MLFLOW_DISABLE_TELEMETRY=true"):
                validate_runtime_environment()
        with patch.dict(os.environ, {"MLFLOW_DISABLE_TELEMETRY": "true"}, clear=True):
            self.assertIsNone(validate_runtime_environment())
            self.assertEqual(os.environ.get("MLFLOW_GENAI_EVAL_MAX_WORKERS"), "1")
            self.assertEqual(
                os.environ.get("MLFLOW_GENAI_EVAL_MAX_SCORER_WORKERS"), "1"
            )

    def test_explicit_worker_settings_are_preserved_and_can_be_logged(self):
        settings = {
            "MLFLOW_DISABLE_TELEMETRY": "true",
            "MLFLOW_GENAI_EVAL_MAX_WORKERS": "2",
            "MLFLOW_GENAI_EVAL_MAX_SCORER_WORKERS": "2",
        }
        with patch.dict(os.environ, settings, clear=True):
            validate_runtime_environment()
            self.assertEqual(os.environ["MLFLOW_GENAI_EVAL_MAX_WORKERS"], "2")
            self.assertEqual(os.environ["MLFLOW_GENAI_EVAL_MAX_SCORER_WORKERS"], "2")

    def test_pool_impossibility_respects_page_coordinates(self):
        result = search_oracle(
            [self.doc("wrong", 2, 0, 10)], [], self.gold, self.pages, lambda _: 1
        )
        self.assertEqual(result["status"], "IMPOSSIBLE_POOL")

    def test_combined_witness_obeys_exact_budget(self):
        docs = [self.doc("one", 1, 0, 4), self.doc("two", 1, 4, 10)]
        result = search_oracle(docs, [], self.gold, self.pages, lambda _: 2048)
        self.assertEqual(result["status"], "FOUND")
        self.assertEqual([d["chunk_id"] for d in result["documents"]], ["one", "two"])
        self.assertEqual(result["token_count"], 2048)
        self.assertEqual(
            search_oracle(docs, [], self.gold, self.pages, lambda _: 2049)["status"],
            "UNKNOWN",
        )

    def test_timeout_is_unknown_not_impossible(self):
        result = search_oracle(
            [self.doc("one", 1, 0, 10)],
            [],
            self.gold,
            self.pages,
            lambda _: 1,
            seconds=0,
        )
        self.assertEqual(result["status"], "UNKNOWN")
        self.assertEqual(result["reason"], "timeout")


if __name__ == "__main__":
    unittest.main()
