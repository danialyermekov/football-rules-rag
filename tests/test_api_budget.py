import tempfile
import unittest
from pathlib import Path

from football_rules.evaluation.budget import ApiBudget


class ApiBudgetTests(unittest.TestCase):
    def test_reservation_survives_restart_and_blocks_before_request(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "budget.jsonl"
            budget = ApiBudget(path, 0.015, 0.75, 3.75)
            index = budget.reserve(100, 2048)
            reloaded = ApiBudget(path, 0.015, 0.75, 3.75)
            with self.assertRaisesRegex(RuntimeError, "no new request"):
                reloaded.reserve(100, 2048)
            reloaded.settle(
                index,
                {
                    "prompt_token_count": 100,
                    "candidates_token_count": 10,
                    "thoughts_token_count": 20,
                },
            )
            self.assertAlmostEqual(reloaded.charged(), (100 * 0.75 + 30 * 3.75) / 1e6)
            reloaded.reserve(100, 2048)

    def test_unknown_usage_keeps_reservation_and_thinking_is_charged(self):
        with tempfile.TemporaryDirectory() as directory:
            budget = ApiBudget(Path(directory) / "ledger.jsonl", 0.1, 0.1, 0.4)
            index = budget.reserve(1000, 2048)
            original = budget.charged()
            with self.assertRaises(ValueError):
                budget.settle(index, {})
            self.assertEqual(budget.charged(), original)
            budget.settle(
                index,
                {
                    "promptTokenCount": 100,
                    "candidatesTokenCount": 20,
                    "thoughtsTokenCount": 30,
                },
            )
            self.assertAlmostEqual(budget.charged(), (100 * 0.1 + 50 * 0.4) / 1e6)
