import unittest
from unittest.mock import Mock

import mlflow

from football_rules.reranking import (
    QWEN_INSTRUCTION,
    CrossEncoderReranker,
    rank_documents,
)


class RerankingTests(unittest.TestCase):
    def setUp(self):
        original_tracking_uri = mlflow.get_tracking_uri()
        mlflow.set_tracking_uri("sqlite:///:memory:")
        self.addCleanup(mlflow.set_tracking_uri, original_tracking_uri)
        mlflow.tracing.disable()
        self.addCleanup(mlflow.tracing.enable)
        self.documents = [
            {"chunk_id": "b", "text": "ball", "score": 0.9},
            {"chunk_id": "a", "text": "referee", "score": 0.8},
        ]

    def fixture(self):
        reranker = CrossEncoderReranker.__new__(CrossEncoderReranker)
        reranker.max_tokens = 10
        reranker.model_name = "bge"
        reranker.batch_size = 2
        reranker.model = Mock()
        reranker.model.tokenizer.return_value = {"input_ids": [[1, 2, 3], [1, 2]]}
        reranker.model.predict.return_value = [-2.0, 5.0]
        return reranker

    def test_scores_order_ties_metadata_and_input_unchanged(self):
        ranked = rank_documents(self.documents, [-2, 5])
        self.assertEqual([hit["chunk_id"] for hit in ranked], ["a", "b"])
        self.assertEqual(ranked[0]["retrieval_score"], 0.8)
        self.assertEqual(ranked[0]["score"], 5)
        self.assertEqual(self.documents[1]["score"], 0.8)
        self.assertEqual(
            [hit["chunk_id"] for hit in rank_documents(self.documents, [1, 1])],
            ["a", "b"],
        )

    def test_invalid_scores_rejected(self):
        for scores in ([1], [float("nan"), 2], [1, float("inf")]):
            with self.assertRaises(ValueError):
                rank_documents(self.documents, scores)

    def test_full_pairs_sent_without_truncation_and_logits_rerank(self):
        reranker = self.fixture()
        ranked = reranker.rerank("is it a goal?", self.documents)
        expected = [("is it a goal?", "ball"), ("is it a goal?", "referee")]
        reranker.model.tokenizer.assert_called_once_with(expected, truncation=False)
        self.assertEqual(reranker.model.predict.call_args.args[0], expected)
        self.assertEqual(ranked[0]["chunk_id"], "a")

    def test_overflow_rejected_before_inference(self):
        reranker = self.fixture()
        reranker.model.tokenizer.return_value = {"input_ids": [[1] * 11, [1]]}
        with self.assertRaises(ValueError):
            reranker.rerank("question", self.documents)
        reranker.model.predict.assert_not_called()

    def test_qwen_checks_full_chat_and_uses_same_instruction_for_prediction(self):
        import torch

        reranker = self.fixture()
        reranker.model_name = "qwen3-0.6b"
        reranker.model.preprocess.return_value = {
            "attention_mask": torch.tensor([[1, 1, 1], [0, 1, 1]])
        }
        self.assertEqual(
            reranker.rerank("question", self.documents)[0]["chunk_id"], "a"
        )
        options = {
            "prompt": QWEN_INSTRUCTION,
            "processing_kwargs": {"text": {"truncation": False}},
        }
        reranker.model.preprocess.assert_called_once_with(
            [("question", "ball"), ("question", "referee")], **options
        )
        for key, value in options.items():
            self.assertEqual(reranker.model.predict.call_args.kwargs[key], value)
        reranker.model.tokenizer.assert_not_called()

        reranker.model.predict.reset_mock()
        reranker.model.preprocess.return_value = {
            "attention_mask": torch.ones((2, 11), dtype=torch.int64)
        }
        with self.assertRaises(ValueError):
            reranker.rerank("question", self.documents)
        reranker.model.predict.assert_not_called()

    def test_empty_candidates_and_invalid_inputs(self):
        reranker = self.fixture()
        self.assertEqual(reranker.rerank("question", []), [])
        reranker.model.predict.assert_not_called()
        for query, documents in [
            (" ", self.documents),
            ("question", [self.documents[0]] * 2),
            ("question", [{**self.documents[0], "text": " "}]),
        ]:
            with self.assertRaises(ValueError):
                reranker.rerank(query, documents)


if __name__ == "__main__":
    unittest.main()
