import math
import tempfile
import unittest
from pathlib import Path

import mlflow

from football_rules.io import write_jsonl
from football_rules.retrieval.bm25 import BM25Retriever, tokenize


class BM25Tests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / "chunks.jsonl"
        original_tracking_uri = mlflow.get_tracking_uri()
        mlflow.set_tracking_uri("sqlite:///:memory:")
        self.addCleanup(mlflow.set_tracking_uri, original_tracking_uri)
        mlflow.tracing.disable()
        self.addCleanup(mlflow.tracing.enable)

    def build(self, records):
        write_jsonl(self.path, records)
        return BM25Retriever(self.path)

    def test_unicode_normalization_preserves_numbers_and_negation(self):
        self.assertEqual(
            tokenize("НЕ: ёлка, Е\u0308ЛКА; Law_12 — １０!"),
            ["не", "елка", "елка", "law", "12", "10"],
        )

    def test_scores_match_hand_calculation_and_length_normalization(self):
        retriever = self.build(
            [
                {"chunk_id": "a", "text": "ball ball", "language": "en"},
                {"chunk_id": "b", "text": "ball referee goal kick", "language": "en"},
                {"chunk_id": "c", "text": "referee", "language": "en"},
            ]
        )
        hits = retriever.search("ball", "en")
        self.assertEqual([hit["chunk_id"] for hit in hits], ["a", "b"])
        idf = math.log(1 + (3 - 2 + 0.5) / (2 + 0.5))
        expected = idf * 2 * 2.2 / (2 + 1.2 * (0.25 + 0.75 * 2 / (7 / 3)))
        self.assertAlmostEqual(hits[0]["score"], expected)
        self.assertEqual(hits, retriever.search("ball ball", "en"))

    def test_language_statistics_are_independent_and_ties_are_stable(self):
        english = [
            {"chunk_id": "b", "text": "ball", "language": "en"},
            {"chunk_id": "a", "text": "ball", "language": "en"},
        ]
        first = self.build(english).search("ball", "en")
        mixed = self.build(
            english + [{"chunk_id": "ru", "text": "ball мяч " * 20, "language": "ru"}]
        )
        self.assertEqual(first, mixed.search("ball", "en"))
        self.assertEqual([hit["chunk_id"] for hit in first], ["a", "b"])
        self.assertEqual(len(mixed.search("ball", "en", 1)), 1)
        self.assertEqual(mixed.search("unknown", "en"), [])
        self.assertEqual(mixed.search("!!!", "en"), [])
        self.assertEqual(mixed.search("мяч", "en"), [])
        self.assertEqual(mixed.search("мяч", "ru")[0]["chunk_id"], "ru")

    def test_empty_language_and_tokenless_corpus(self):
        retriever = self.build([{"chunk_id": "a", "text": "!!!", "language": "en"}])
        self.assertEqual(retriever.search("ball", "en"), [])
        self.assertEqual(retriever.search("мяч", "ru"), [])

    def test_stemming_matches_inflections_on_both_sides_and_preserves_numbers(self):
        write_jsonl(
            self.path,
            [
                {"chunk_id": "ru", "text": "игроками мячом не 12", "language": "ru"},
                {"chunk_id": "en", "text": "players handling not 12", "language": "en"},
            ],
        )
        plain = BM25Retriever(self.path)
        stemmed = BM25Retriever(self.path, stemming=True)
        self.assertEqual(plain.search("игрок", "ru"), [])
        self.assertEqual(plain.search("player", "en"), [])
        self.assertEqual(stemmed.search("игрок", "ru")[0]["chunk_id"], "ru")
        self.assertEqual(stemmed.search("player", "en")[0]["chunk_id"], "en")
        self.assertEqual(stemmed._tokenize("не 12", "ru"), ["не", "12"])
        self.assertEqual(stemmed._tokenize("not 12", "en"), ["not", "12"])
        self.assertEqual(
            stemmed.search("player player", "en"), stemmed.search("player", "en")
        )
        self.assertFalse(plain.manifest["stemming"])
        self.assertEqual(stemmed.manifest["stemming"], "snowball")

    def test_invalid_inputs_and_duplicate_ids_are_rejected(self):
        record = {"chunk_id": "a", "text": "ball", "language": "en"}
        retriever = self.build([record])

        for query, language, k in [
            (" ", "en", 1),
            ("ball", "de", 1),
            ("ball", "en", 0),
        ]:
            with self.assertRaises(ValueError):
                retriever.search(query, language, k)

        for records in [[], [record, record], [{**record, "language": "de"}]]:
            with self.assertRaises(ValueError):
                self.build(records)


if __name__ == "__main__":
    unittest.main()
