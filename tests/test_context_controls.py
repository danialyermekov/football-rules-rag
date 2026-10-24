import unittest

from football_rules.context_controls import citation_integrity, retain_context_pages


class ContextControlTests(unittest.TestCase):
    def setUp(self):
        self.documents = [
            {"document_id": "en", "pdf_page": 1, "text": "relevant"},
            {"document_id": "en", "pdf_page": 2, "text": "audited remnant"},
            {"document_id": "en", "pdf_page": 2, "text": "second chunk"},
        ]

    def test_ablation_preserves_original_payload_and_order(self):
        result = retain_context_pages(self.documents, [2], {("en", 1)})
        self.assertEqual(result, self.documents[1:])
        self.assertIs(result[0], self.documents[1])
        self.assertEqual(len(self.documents), 3)

    def test_ablation_rejects_gold_page_empty_and_unchanged_context(self):
        for pages, required in [([1], {("en", 1)}), ([3], set()), ([1, 2], set())]:
            with self.subTest(pages=pages), self.assertRaises(ValueError):
                retain_context_pages(self.documents, pages, required)

    def test_citation_integrity_allows_empty_but_rejects_invented_pages(self):
        for citations, expected in [
            ([], True),
            (["en:2"], True),
            (["en:3"], False),
            (["ru:2"], False),
            (["en:2", "en:2"], False),
        ]:
            with self.subTest(citations=citations):
                self.assertEqual(
                    citation_integrity(
                        {"citations": citations, "documents": self.documents}
                    ),
                    expected,
                )
