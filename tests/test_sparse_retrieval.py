import unittest
from unittest.mock import Mock

import mlflow

from football_rules.sparse_retrieval import BGESparseRetriever, lexical_weights


class SparseRetrievalTests(unittest.TestCase):
    def setUp(self):
        original_tracking_uri = mlflow.get_tracking_uri()
        mlflow.set_tracking_uri("sqlite:///:memory:")
        self.addCleanup(mlflow.set_tracking_uri, original_tracking_uri)
        mlflow.tracing.disable()
        self.addCleanup(mlflow.tracing.enable)

    def test_weights_use_max_exclude_special_tokens_and_drop_nonpositive(self):
        self.assertEqual(
            lexical_weights([0, 10, 10, 20, 30, 2], [99, 0.2, 0.7, 0, -1, 99], {0, 2}),
            {"10": 0.7},
        )
        for values in ([1], [float("nan"), 1], [1, float("inf")]):
            with self.assertRaises(ValueError):
                lexical_weights([10, 20], values, set())

    def test_search_dot_product_language_filter_ties_and_zero_exclusion(self):
        retriever = BGESparseRetriever.__new__(BGESparseRetriever)
        retriever.documents = [
            {"chunk_id": "b", "language": "en", "text": "b"},
            {"chunk_id": "a", "language": "en", "text": "a"},
            {"chunk_id": "ru", "language": "ru", "text": "мяч"},
            {"chunk_id": "zero", "language": "en", "text": "zero"},
        ]
        retriever.vectors = [{"10": 2.0}, {"10": 1.0, "20": 2.0}, {"10": 99}, {}]
        retriever.encode = Mock(return_value=[{"10": 2.0, "20": 1.0}])
        hits = retriever.search("ball", "en", 10)
        self.assertEqual([hit["chunk_id"] for hit in hits], ["a", "b"])
        self.assertEqual([hit["score"] for hit in hits], [4.0, 4.0])
        self.assertEqual(len(retriever.search("ball", "en", 1)), 1)
        self.assertEqual(retriever.search("мяч", "ru")[0]["chunk_id"], "ru")
        retriever.encode.reset_mock()
        for query, language, k in [
            (" ", "en", 1),
            ("ball", "de", 1),
            ("ball", "en", 0),
        ]:
            with self.assertRaises(ValueError):
                retriever.search(query, language, k)
        retriever.encode.assert_not_called()


if __name__ == "__main__":
    unittest.main()
