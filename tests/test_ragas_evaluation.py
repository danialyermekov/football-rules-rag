import unittest
from unittest.mock import Mock

from football_rules.ragas_evaluation import (
    LocalMetricEmbeddings,
    checked_score,
    metric_applicability,
)


class RagasEvaluationTests(unittest.IsolatedAsyncioTestCase):
    async def test_local_embeddings_use_same_symmetric_encoding_for_questions(self):
        encoder = Mock()
        encoder.encode.side_effect = [[[1.0, 0.0]], [[0.0, 1.0], [1.0, 0.0]]]
        embeddings = LocalMetricEmbeddings(encoder)
        self.assertEqual(await embeddings.aembed_text("original"), [1.0, 0.0])
        self.assertEqual(
            await embeddings.aembed_texts(["generated1", "generated2"]),
            [[0.0, 1.0], [1.0, 0.0]],
        )
        encoder.encode_queries.assert_not_called()

    def test_missing_context_is_na_without_suppressing_answer_relevancy(self):
        for name in ["context_precision", "context_recall", "faithfulness"]:
            self.assertIsNotNone(metric_applicability(name, []))
            self.assertIsNone(metric_applicability(name, [{"text": "rule"}]))
        self.assertIsNone(metric_applicability("answer_relevancy", []))

    def test_undefined_scores_remain_na_and_errors_are_not_zeroed(self):
        self.assertIsNone(checked_score(float("nan"), "faithfulness"))
        self.assertEqual(checked_score(-0.2, "answer_relevancy"), -0.2)
        for value in [float("inf"), -0.1, 1.1]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                checked_score(value, "context_precision")
