import unittest

from football_rules.evidence_evaluation import pack_anchor_first_context


def doc(identity, text):
    return {
        "chunk_id": identity,
        "document_id": "law",
        "pdf_page": 1,
        "printed_page": 1,
        "text": text,
    }


class AnchorFirstPackingTests(unittest.TestCase):
    def setUp(self):
        self.documents = [
            doc("a", "anchor"),
            doc("p", "previous first second third"),
            doc("s", "successor"),
        ]
        self.links = {"p": "a", "a": "s"}

    def tokens(self, text):
        return len(text.split())

    def test_anchor_is_not_displaced_by_earlier_source_neighbor(self):
        # Labels cost three words; anchor and successor each cost four total.
        result = pack_anchor_first_context(self.documents, self.links, 8, self.tokens)
        self.assertEqual([d["chunk_id"] for d in result["documents"]], ["a", "s"])
        self.assertEqual(result["token_count"], 8)
        self.assertEqual(
            result["skipped"], [{"chunk_id": "p", "reason": "token_budget"}]
        )
        self.assertEqual([d["chunk_id"] for d in self.documents], ["a", "p", "s"])

    def test_admission_order_differs_from_display_order(self):
        result = pack_anchor_first_context(self.documents, self.links, 15, self.tokens)
        self.assertEqual([d["chunk_id"] for d in result["documents"]], ["p", "a", "s"])
        self.assertEqual(result["token_count"], 15)
        self.assertEqual(result["skipped"], [])

    def test_rejected_anchor_does_not_block_fitting_neighbors(self):
        documents = [doc("a", "anchor is oversized"), doc("s", "successor")]
        result = pack_anchor_first_context(documents, {"a": "s"}, 4, self.tokens)
        self.assertEqual([d["chunk_id"] for d in result["documents"]], ["s"])
        self.assertEqual(
            result["skipped"], [{"chunk_id": "a", "reason": "token_budget"}]
        )

    def test_counts_the_whole_candidate_text_not_individual_chunks(self):
        def tokens(text):
            return 4 if "anchor" in text and "successor" in text else 1

        result = pack_anchor_first_context(
            [doc("a", "anchor"), doc("s", "successor")], {"a": "s"}, 2, tokens
        )
        self.assertEqual([d["chunk_id"] for d in result["documents"]], ["a"])
        self.assertEqual(result["token_count"], 1)

    def test_missing_neighbors_are_not_fetched_and_empty_pool_is_valid(self):
        result = pack_anchor_first_context(
            [doc("a", "anchor")], {"outside": "a", "a": "missing"}, 4, self.tokens
        )
        self.assertEqual([d["chunk_id"] for d in result["documents"]], ["a"])
        self.assertEqual(
            pack_anchor_first_context([], {}, 4, self.tokens),
            {"documents": [], "text": "", "token_count": 0, "skipped": []},
        )

    def test_invalid_pool_links_and_budget_are_rejected(self):
        with self.assertRaises(ValueError):
            pack_anchor_first_context([doc("a", "a")] * 2, {}, 4, self.tokens)
        with self.assertRaises(ValueError):
            pack_anchor_first_context([], {"a": "c", "b": "c"}, 4, self.tokens)
        with self.assertRaises(ValueError):
            pack_anchor_first_context([], {}, 0, self.tokens)


if __name__ == "__main__":
    unittest.main()
