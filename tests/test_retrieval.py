import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

import mlflow

from football_rules.embeddings import BGEEmbedder
from football_rules.jsonl import write_jsonl
from football_rules.retrieval import (
    DenseRetriever,
    index_chunks,
    read_chunks,
    validate_vectors,
)
from football_rules.retrieval_metrics import ranking_metrics, relevant_chunks


class FixtureEmbedder:
    dimension = 2

    def __init__(self):
        self.calls = 0
        self.query_calls = 0

    def parameters(self):
        return {"model": "test-fixture", "dimension": self.dimension}

    def encode(self, texts):
        self.calls += 1
        return [
            [1.0, 0.0] if "ball" in text or "мяч" in text else [0.0, 1.0]
            for text in texts
        ]

    def encode_queries(self, texts):
        self.query_calls += 1
        return self.encode(texts)


class RetrievalTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.chunks = self.root / "chunks.jsonl"
        self.database = self.root / "qdrant"
        self.embedder = FixtureEmbedder()
        original_tracking_uri = mlflow.get_tracking_uri()
        mlflow.set_tracking_uri("sqlite:///:memory:")
        self.addCleanup(mlflow.set_tracking_uri, original_tracking_uri)
        self.records = [
            {"chunk_id": "a", "text": "ball", "language": "en", "pdf_page": 1},
            {"chunk_id": "b", "text": "мяч", "language": "ru", "pdf_page": 2},
            {"chunk_id": "c", "text": "referee", "language": "en", "pdf_page": 3},
        ]
        write_jsonl(self.chunks, self.records)
        mlflow.tracing.disable()
        self.addCleanup(mlflow.tracing.enable)

    def test_persistent_index_language_filter_and_idempotent_reuse(self):
        report = index_chunks(self.chunks, self.database, self.embedder)
        self.assertFalse(report["reused"])
        repeated = index_chunks(self.chunks, self.database, self.embedder)
        self.assertTrue(repeated["reused"])
        self.assertEqual(self.embedder.calls, 1)
        self.assertEqual(self.embedder.query_calls, 0)
        retriever = DenseRetriever(self.database, report["collection"], self.embedder)

        try:
            hits = retriever.search("ball", "en", 2)
            self.assertEqual([hit["chunk_id"] for hit in hits], ["a", "c"])
            self.assertAlmostEqual(hits[0]["score"], 1.0)
            self.assertEqual(hits[0]["pdf_page"], 1)
            self.assertEqual(
                [hit["chunk_id"] for hit in retriever.search("мяч", "ru")], ["b"]
            )
            self.assertEqual(self.embedder.query_calls, 2)

            for query, language, k in [
                ("", "en", 1),
                ("ball", "de", 1),
                ("ball", "en", 0),
            ]:
                with self.assertRaises(ValueError):
                    retriever.search(query, language, k)
        finally:
            retriever.close()

    def test_new_corpus_has_new_collection_and_original_is_preserved(self):
        first = index_chunks(self.chunks, self.database, self.embedder)
        write_jsonl(self.chunks, self.records[:1])
        second = index_chunks(self.chunks, self.database, self.embedder)
        self.assertNotEqual(first["collection"], second["collection"])
        self.assertTrue((self.database / f"{first['collection']}.json").exists())

    def test_interrupted_index_can_be_completed_without_deletion(self):
        report = index_chunks(self.chunks, self.database, self.embedder)
        (self.database / f"{report['collection']}.json").unlink()
        recovered = index_chunks(self.chunks, self.database, self.embedder)
        self.assertFalse(recovered["reused"])
        self.assertEqual(recovered["points"], 3)

    def test_embedding_mismatch_and_modified_manifest_are_rejected(self):
        report = index_chunks(self.chunks, self.database, self.embedder)
        self.embedder.dimension = 3
        with self.assertRaisesRegex(ValueError, "differs"):
            DenseRetriever(self.database, report["collection"], self.embedder)

        self.embedder.dimension = 2
        path = self.database / f"{report['collection']}.json"
        path.write_text("{}", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "manifest differs"):
            index_chunks(self.chunks, self.database, self.embedder)

    def test_invalid_chunks_and_vectors_are_rejected(self):
        for records in [
            [],
            self.records + self.records[:1],
            [{"chunk_id": "d", "text": " "}],
        ]:
            write_jsonl(self.chunks, records)
            with self.assertRaises(ValueError):
                read_chunks(self.chunks)

        for vectors in [[], [[1.0]], [[float("nan"), 1.0]], [[0.0, 0.0]]]:
            with self.assertRaises(ValueError):
                validate_vectors(vectors, 1, 2)


class EmbeddingTests(unittest.TestCase):
    def test_missing_model_is_rejected_before_loading_weights(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            with self.assertRaisesRegex(ValueError, "Download"):
                BGEEmbedder(path)
            (path / "config.json").write_text("{}", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "pinned revision"):
                BGEEmbedder(path)

    def test_empty_input_and_token_truncation_are_rejected(self):
        embedder = BGEEmbedder.__new__(BGEEmbedder)
        embedder.model = MagicMock()
        embedder.model.max_seq_length = 4
        embedder.max_tokens = 4
        embedder.batch_size = 4

        for texts in [[], [" "]]:
            with self.assertRaises(ValueError):
                embedder.encode(texts)

        embedder.model.tokenizer.return_value = {"input_ids": [[1, 2, 3, 4, 5]]}
        with self.assertRaisesRegex(ValueError, "token limit"):
            embedder.encode(["a very long input"])
        embedder.model.encode.assert_not_called()

        embedder.model.tokenizer.return_value = {"input_ids": [[1, 2]]}
        embedder.model.encode.return_value.tolist.return_value = [[1.0, 0.0]]
        self.assertEqual(embedder.encode(["ball"]), [[1.0, 0.0]])


class RankingMetricTests(unittest.TestCase):
    def test_known_ranking_values(self):
        metrics = ranking_metrics(["irrelevant", "a", "b"], ["a", "b"], 3)
        self.assertEqual(metrics["recall"], 1)
        self.assertAlmostEqual(metrics["precision"], 2 / 3)
        self.assertEqual(metrics["mrr"], 0.5)
        self.assertAlmostEqual(metrics["ndcg"], 0.6934264036)
        self.assertEqual(ranking_metrics(["a"], [], 5)["recall"], 0)
        self.assertEqual(ranking_metrics([], ["a"], 5)["ndcg"], 0)

        for retrieved, k in [(["a", "a"], 5), (["a"], 0)]:
            with self.assertRaises(ValueError):
                ranking_metrics(retrieved, ["a"], k)

    def test_qrels_require_sufficient_source_coverage_and_exact_document(self):
        pages = {
            ("doc", 1): {
                "text": "12345 abcde",
                "removed_spans": [{"start": 0, "end": 5}],
            }
        }
        locators = [
            {"document_id": "doc", "pdf_page": 1, "char_start": 0, "char_end": 11}
        ]
        chunks = [
            {
                "chunk_id": "enough",
                "document_id": "doc",
                "pdf_page": 1,
                "source_spans": [{"start": 6, "end": 10}],
            },
            {
                "chunk_id": "partial",
                "document_id": "doc",
                "pdf_page": 1,
                "source_spans": [{"start": 6, "end": 9}],
            },
            {
                "chunk_id": "other",
                "document_id": "another",
                "pdf_page": 1,
                "source_spans": [{"start": 6, "end": 11}],
            },
        ]
        self.assertEqual(relevant_chunks(chunks, locators, pages), ["enough"])
        with self.assertRaises(ValueError):
            relevant_chunks(chunks, [], pages)
        with self.assertRaises(ValueError):
            relevant_chunks(chunks, locators, pages, 0)

        locators[0]["char_end"] = 5
        with self.assertRaisesRegex(ValueError, "no retained"):
            relevant_chunks(chunks, locators, pages)


if __name__ == "__main__":
    unittest.main()
