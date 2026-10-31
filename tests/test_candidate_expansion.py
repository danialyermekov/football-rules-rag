import copy
import importlib
import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pandas as pd

from football_rules.candidate_expansion import (
    merge_reranked_candidates,
    tail_candidates,
)
from football_rules.reranking import rank_documents


def raw(identity, score):
    return {"chunk_id": identity, "text": identity + " passage", "score": score}


class CandidateExpansionTests(unittest.TestCase):
    def setUp(self):
        self.fused = [raw("a", 0.03), raw("b", 0.02), raw("c", 0.01), raw("d", 0.005)]
        self.prefix = rank_documents(self.fused[:2], [1.0, 2.0])
        self.tail = rank_documents(self.fused[2:], [3.0, 0.0])

    def test_tail_is_original_suffix_not_cached_reranker_order(self):
        self.assertEqual([d["chunk_id"] for d in self.prefix], ["b", "a"])
        self.assertEqual(tail_candidates(self.fused, self.prefix), self.fused[2:])

    def test_common_ranking_uses_only_compatible_reranker_scores(self):
        before = copy.deepcopy((self.fused, self.prefix, self.tail))
        result = merge_reranked_candidates(self.fused, self.prefix, self.tail)
        self.assertEqual([d["chunk_id"] for d in result], ["c", "b", "a", "d"])
        self.assertEqual([d["score"] for d in result], [3.0, 2.0, 1.0, 0.0])
        self.assertEqual(result[0]["retrieval_score"], 0.01)
        self.assertEqual(result[1], self.prefix[0])
        self.assertEqual((self.fused, self.prefix, self.tail), before)

    def test_score_ties_use_chunk_id_not_input_stage(self):
        prefix = rank_documents(self.fused[:2], [1.0, 1.0])
        tail = rank_documents(self.fused[2:], [1.0, 1.0])
        result = merge_reranked_candidates(self.fused, prefix, tail)
        self.assertEqual([d["chunk_id"] for d in result], ["a", "b", "c", "d"])

    def test_prefix_must_be_exact_scored_source_prefix(self):
        invalid = [
            list(reversed(self.prefix)),
            self.tail,
            [{**self.prefix[0], "text": "changed"}, self.prefix[1]],
            [{**self.prefix[0], "retrieval_score": 99}, self.prefix[1]],
            [{**self.prefix[0], "score": float("nan")}, self.prefix[1]],
        ]
        for prefix in invalid:
            with self.subTest(prefix=prefix), self.assertRaises(ValueError):
                tail_candidates(self.fused, prefix)

    def test_tail_must_have_exact_membership_order_and_provenance(self):
        invalid = [
            self.tail[:1],
            list(reversed(self.tail)),
            [self.tail[0], self.tail[0]],
            [{**self.tail[0], "text": "changed"}, self.tail[1]],
            [{**self.tail[0], "score": float("inf")}, self.tail[1]],
        ]
        for tail in invalid:
            with self.subTest(tail=tail), self.assertRaises(ValueError):
                merge_reranked_candidates(self.fused, self.prefix, tail)

    def test_duplicate_raw_ids_and_missing_prefix_are_rejected(self):
        with self.assertRaises(ValueError):
            tail_candidates([self.fused[0]] * 2, self.prefix)
        with self.assertRaises(ValueError):
            tail_candidates(self.fused, [])

    def test_no_extra_candidates_keeps_original_ranking(self):
        self.assertEqual(tail_candidates(self.fused[:2], self.prefix), [])
        self.assertEqual(
            merge_reranked_candidates(self.fused[:2], self.prefix, []), self.prefix
        )


class NativeDatasetReuseTests(unittest.TestCase):
    def test_dataset_metadata_does_not_enter_frozen_record_serialization(self):
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
        with patch.dict(os.environ, {}, clear=False):
            runner = importlib.import_module("evaluate_full_union_reranker")
        records = [
            {
                "inputs": {"query": "example", "language": "en"},
                "expectations": {"id": "case"},
            }
        ]
        before = copy.deepcopy(records)
        native = Mock()
        native.to_df.return_value = pd.DataFrame(
            [{**records[0], "source": object(), "tags": {"user": "example"}}]
        )
        client = Mock()
        client.search_datasets.return_value = [
            SimpleNamespace(
                name="football-e25-" + runner.digest(records)[:16],
                dataset_id="existing",
            )
        ]
        with patch.object(runner, "get_dataset", return_value=native):
            self.assertIs(runner.native_dataset(client, "1", records), native)
        self.assertEqual(records, before)


if __name__ == "__main__":
    unittest.main()
