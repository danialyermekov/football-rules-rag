import runpy
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


class ReplayConfigurationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        scripts = Path(__file__).resolve().parents[1] / "scripts"
        with patch.object(sys, "path", [str(scripts), *sys.path]):
            cls.configuration = staticmethod(
                runpy.run_path(str(scripts / "evaluate_reranker.py"))[
                    "replay_configuration"
                ]
            )

    def test_dense_configuration_preserves_e3(self):
        parameters = {
            "strategy": "dense",
            "evaluation_protocol": "v2",
            "context_budget": "2048",
        }
        self.assertEqual(
            self.configuration(parameters), ("E3-dense20-reranker-v2", "dense")
        )

    def test_rrf_configuration_requires_matching_fusion(self):
        parameters = {
            "strategy": "hybrid",
            "evaluation_protocol": "v2",
            "context_budget": "2048",
            "fusion_method": "RRF",
            "fusion_rank_constant": "60",
            "fusion_rank_origin": "1",
            "fusion_weights": "equal",
            "branch_depth": "50",
        }
        self.assertEqual(
            self.configuration(parameters), ("E4-rrf20-reranker-v2", "rrf")
        )
        for key in (
            "fusion_method",
            "fusion_rank_constant",
            "fusion_rank_origin",
            "fusion_weights",
            "branch_depth",
        ):
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.configuration({**parameters, key: "different"})

    def test_wrong_strategy_protocol_or_budget_rejected(self):
        parameters = {
            "strategy": "dense",
            "evaluation_protocol": "v2",
            "context_budget": "2048",
        }
        for key, value in [
            ("strategy", "bm25"),
            ("evaluation_protocol", "v1"),
            ("context_budget", "4096"),
        ]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.configuration({**parameters, key: value})


if __name__ == "__main__":
    unittest.main()
