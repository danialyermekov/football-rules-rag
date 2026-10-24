import unittest

from football_rules.evidence_evaluation import chunk_successors, prioritize_successors


def chunk(identity, page=1, start=0, text="rule", **metadata):
    return {
        "chunk_id": identity,
        "document_id": "doc",
        "language": "en",
        "edition": "2026/27",
        "pdf_page": page,
        "cleaned_start": start,
        "text": text,
        **metadata,
    }


class ContextOrderingTests(unittest.TestCase):
    def test_physical_order_is_independent_of_input_rank(self):
        chunks = [chunk("c", start=800), chunk("a"), chunk("b", start=400)]
        self.assertEqual(chunk_successors(chunks), {"a": "b", "b": "c"})

    def test_page_crossing_requires_consecutive_page_and_bullet(self):
        self.assertEqual(
            chunk_successors([chunk("a"), chunk("b", page=2, text="  • continuation")]),
            {"a": "b"},
        )
        for following in [
            chunk("b", page=2, text="2. New section"),
            chunk("b", page=3, text="• list"),
        ]:
            with self.subTest(following=following):
                self.assertEqual(chunk_successors([chunk("a"), following]), {})

    def test_document_language_and_edition_boundaries_are_preserved(self):
        for metadata in [
            {"document_id": "other"},
            {"language": "ru"},
            {"edition": "2025/26"},
        ]:
            with self.subTest(metadata=metadata):
                self.assertEqual(
                    chunk_successors([chunk("a"), chunk("b", start=400, **metadata)]),
                    {},
                )

    def test_promotes_one_hop_and_preserves_original_candidates(self):
        documents = [chunk("a"), chunk("x"), chunk("c"), chunk("b")]
        reordered = prioritize_successors(documents, {"a": "b", "b": "c"})
        self.assertEqual([d["chunk_id"] for d in reordered], ["a", "b", "x", "c"])
        self.assertEqual([d["chunk_id"] for d in documents], ["a", "x", "c", "b"])
        self.assertEqual(
            {d["chunk_id"] for d in reordered}, {d["chunk_id"] for d in documents}
        )
        for document in reordered:
            self.assertIs(
                document,
                next(d for d in documents if d["chunk_id"] == document["chunk_id"]),
            )

    def test_missing_successor_is_not_added_and_anchor_order_is_stable(self):
        documents = [chunk("a"), chunk("b")]
        self.assertEqual(prioritize_successors(documents, {"a": "outside"}), documents)
        self.assertEqual(prioritize_successors([], {}), [])

    def test_duplicate_ids_fail_before_reordering(self):
        duplicate = [chunk("a"), chunk("a", start=400)]
        with self.assertRaises(ValueError):
            chunk_successors(duplicate)
        with self.assertRaises(ValueError):
            prioritize_successors(duplicate, {})
