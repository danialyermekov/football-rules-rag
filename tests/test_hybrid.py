import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

import mlflow

from football_rules.io import write_jsonl
from football_rules.retrieval.bm25 import BM25Retriever
from football_rules.retrieval.hybrid import HybridRetriever, reciprocal_rank_fusion
from football_rules.retrieval.store import DenseRetriever, index_chunks


def hit(identity, score=1.0):
    return {"chunk_id": identity, "score": score, "text": identity}


class HybridTests(unittest.TestCase):
    def setUp(self):
        original_tracking_uri = mlflow.get_tracking_uri()
        mlflow.set_tracking_uri("sqlite:///:memory:")
        self.addCleanup(mlflow.set_tracking_uri, original_tracking_uri)
        mlflow.tracing.disable()
        self.addCleanup(mlflow.tracing.enable)

    def test_rank_formula_union_provenance_and_no_input_mutation(self):
        dense = [hit("a", 0.9), hit("b", 0.8)]
        lexical = [hit("c", 100), hit("b", 20)]
        fused = reciprocal_rank_fusion(dense, lexical)
        self.assertEqual([row["chunk_id"] for row in fused], ["b", "a", "c"])
        self.assertAlmostEqual(fused[0]["score"], 2 / 62)
        self.assertEqual(fused[0]["branch_ranks"], {"dense": 2, "bm25": 2})
        self.assertEqual(fused[0]["branch_scores"], {"dense": 0.8, "bm25": 20})
        self.assertAlmostEqual(fused[1]["score"], 1 / 61)
        self.assertEqual(dense, [hit("a", 0.9), hit("b", 0.8)])
        self.assertEqual(lexical, [hit("c", 100), hit("b", 20)])
        self.assertEqual(
            [
                row["chunk_id"]
                for row in reciprocal_rank_fusion(
                    [hit("a", 1000), hit("b", -5)], lexical
                )
            ],
            ["b", "a", "c"],
        )

    def test_empty_lists_and_duplicate_input_ids(self):
        self.assertEqual(reciprocal_rank_fusion([], []), [])
        self.assertAlmostEqual(
            reciprocal_rank_fusion([], [hit("a")])[0]["score"], 1 / 61
        )
        for dense, lexical in [([hit("a"), hit("a")], []), ([], [hit("b"), hit("b")])]:
            with self.assertRaises(ValueError):
                reciprocal_rank_fusion(dense, lexical)

    def test_sparse_branch_has_accurate_provenance_and_same_rrf_formula(self):
        fused = reciprocal_rank_fusion(
            [hit("a")], [hit("a", 3.0)], lexical_name="bge_m3_sparse"
        )
        self.assertEqual(fused[0]["branch_ranks"], {"dense": 1, "bge_m3_sparse": 1})
        self.assertEqual(
            fused[0]["branch_scores"], {"dense": 1.0, "bge_m3_sparse": 3.0}
        )
        self.assertAlmostEqual(fused[0]["score"], 2 / 61)
        with self.assertRaises(ValueError):
            reciprocal_rank_fusion([], [], lexical_name="dense")

    def test_original_and_rewritten_query_ranks_use_distinct_provenance(self):
        fused = reciprocal_rank_fusion(
            [hit("a"), hit("b")],
            [hit("b"), hit("c")],
            dense_name="original",
            lexical_name="rewritten",
        )
        self.assertEqual([row["chunk_id"] for row in fused], ["b", "a", "c"])
        self.assertEqual(fused[0]["branch_ranks"], {"original": 2, "rewritten": 1})

    def test_mismatched_corpus_is_rejected_and_client_closed(self):
        dense = Mock(spec=DenseRetriever)
        dense.manifest = {"chunks_sha256": "one"}
        lexical = Mock(spec=BM25Retriever)
        lexical.manifest = {"chunks_sha256": "two"}
        with self.assertRaises(ValueError):
            HybridRetriever(dense, lexical)
        dense.close.assert_called_once()

    def test_real_qdrant_bm25_composition_language_filter_and_full_union(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        path = root / "chunks.jsonl"
        write_jsonl(
            path,
            [
                {"chunk_id": "a", "text": "ball", "language": "en"},
                {"chunk_id": "b", "text": "referee", "language": "en"},
                {"chunk_id": "ru", "text": "мяч", "language": "ru"},
            ],
        )
        embedder = Mock()
        embedder.dimension = 2
        embedder.parameters.return_value = {"model": "fixture"}
        embedder.encode.side_effect = lambda texts: [
            [0.0, 1.0] if "referee" in text else [1.0, 0.0] for text in texts
        ]
        embedder.encode_queries.side_effect = embedder.encode.side_effect
        manifest = index_chunks(path, root / "qdrant", embedder)
        dense = DenseRetriever(root / "qdrant", manifest["collection"], embedder)
        hybrid = HybridRetriever(dense, BM25Retriever(path))
        self.addCleanup(hybrid.close)
        hits = hybrid.search("ball referee", "en", 1)
        self.assertEqual({row["chunk_id"] for row in hits}, {"a", "b"})
        self.assertEqual(len(hits), 2)
        self.assertTrue(all(row["language"] == "en" for row in hits))
        self.assertEqual(hybrid.search("мяч", "ru")[0]["chunk_id"], "ru")
        with self.assertRaises(ValueError):
            hybrid.search("ball", "en", 0)


if __name__ == "__main__":
    unittest.main()
