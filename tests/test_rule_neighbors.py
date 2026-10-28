import unittest

from football_rules.evidence_evaluation import (
    chunk_successors,
    prioritize_rule_neighbors,
)


class RuleNeighborTests(unittest.TestCase):
    def test_one_hop_only_same_pool_and_unique(self):
        documents = [{"chunk_id": k} for k in ["c", "a", "b", "d", "z"]]
        links = {"a": "b", "b": "c", "c": "d", "d": "missing"}
        result = prioritize_rule_neighbors(documents, links)
        self.assertEqual([r["chunk_id"] for r in result], ["b", "c", "d", "a", "z"])
        self.assertEqual({r["chunk_id"] for r in result}, set("abcdz"))
        self.assertEqual(documents[0]["chunk_id"], "c")

    def test_reject_duplicates_and_ambiguous_predecessors(self):
        with self.assertRaises(ValueError):
            prioritize_rule_neighbors([{"chunk_id": "a"}] * 2, {})
        with self.assertRaises(ValueError):
            prioritize_rule_neighbors([], {"a": "c", "b": "c"})

    def test_links_do_not_cross_document_or_uncontinued_page(self):
        def chunk(key, doc, page, text):
            return {
                "chunk_id": key,
                "document_id": doc,
                "language": "ru",
                "edition": "2026/27",
                "pdf_page": page,
                "cleaned_start": 0,
                "text": text,
            }

        chunks = [
            chunk("a", "one", 1, "heading"),
            chunk("b", "one", 2, "• continuation"),
            chunk("c", "one", 3, "new section"),
            chunk("d", "two", 1, "• other document"),
        ]
        self.assertEqual(chunk_successors(chunks), {"a": "b"})
