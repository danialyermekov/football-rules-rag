import runpy
import unittest
from pathlib import Path

from football_rules.evidence_evaluation import (
    evidence_metrics,
    pack_context,
    render_context,
)


def document(identity, start, end, page=1, source="doc", text=None):
    return {
        "chunk_id": identity,
        "document_id": source,
        "pdf_page": page,
        "printed_page": page,
        "source_spans": [{"start": start, "end": end}],
        "text": text if text is not None else "abcdefghij"[start:end],
    }


def locator(page=1, source="doc", start=0, end=10):
    return {
        "document_id": source,
        "pdf_page": page,
        "char_start": start,
        "char_end": end,
    }


class EvidenceMetricTests(unittest.TestCase):
    def setUp(self):
        self.pages = {
            (source, page): {"text": "abcdefghij", "removed_spans": []}
            for source, page in [("doc", 1), ("doc", 2), ("other", 1)]
        }

    def test_union_recovers_evidence_split_across_chunks(self):
        required = [{"id": "rule", "locators": [locator()]}]
        chunks = [document("a", 0, 6), document("b", 4, 10)]
        values = evidence_metrics(chunks, required, self.pages)
        self.assertEqual(values["complete_evidence"], 1)
        self.assertEqual(values["strict_complete_evidence"], 1)
        self.assertEqual(values["evidence_coverage"], 1)
        self.assertAlmostEqual(values["source_redundancy"], 1 / 6)

    def test_missing_second_locator_cannot_be_compensated(self):
        required = [{"id": "two_pages", "locators": [locator(), locator(page=2)]}]
        values = evidence_metrics([document("a", 0, 10)], required, self.pages)
        self.assertEqual(values["evidence_coverage"], 0.5)
        self.assertEqual(values["evidence_recall"], 0)
        self.assertEqual(values["complete_evidence"], 0)

    def test_all_required_units_are_necessary(self):
        required = [
            {"id": "a", "locators": [locator()]},
            {"id": "b", "locators": [locator(page=2)]},
        ]
        values = evidence_metrics([document("a", 0, 10)], required, self.pages)
        self.assertEqual(values["evidence_recall"], 0.5)
        self.assertEqual(values["complete_evidence"], 0)

    def test_threshold_and_strict_completeness_are_distinct(self):
        required = [{"id": "rule", "locators": [locator()]}]
        values = evidence_metrics([document("a", 0, 8)], required, self.pages)
        self.assertEqual(values["evidence_coverage"], 0.8)
        self.assertEqual(values["complete_evidence"], 1)
        self.assertEqual(values["strict_complete_evidence"], 0)

    def test_same_offsets_in_other_document_or_page_are_not_matches(self):
        required = [{"id": "rule", "locators": [locator()]}]
        chunks = [document("a", 0, 10, source="other"), document("b", 0, 10, page=2)]
        self.assertEqual(
            evidence_metrics(chunks, required, self.pages)["evidence_recall"], 0
        )

    def test_noise_whitespace_and_duplicate_positions(self):
        pages = {
            ("doc", 1): {"text": "12 ab cd", "removed_spans": [{"start": 0, "end": 2}]}
        }
        required = [{"id": "rule", "locators": [locator(end=8)]}]
        chunks = [document("a", 3, 5), document("b", 3, 5)]
        values = evidence_metrics(chunks, required, pages)
        self.assertEqual(values["evidence_coverage"], 0.5)
        self.assertEqual(values["source_redundancy"], 0.5)

    def test_empty_context_has_zero_coverage(self):
        values = evidence_metrics(
            [], [{"id": "rule", "locators": [locator()]}], self.pages
        )
        self.assertTrue(all(value == 0 for value in values.values()))

    def test_invalid_gold_ranges_and_threshold_are_rejected(self):
        required = [{"id": "rule", "locators": [locator()]}]
        for threshold in [0, 1.1]:
            with self.assertRaises(ValueError):
                evidence_metrics([], required, self.pages, threshold)

        for gold in [
            [],
            [{"id": "a", "locators": []}],
            [{"id": "a", "locators": [locator(end=11)]}],
        ]:
            with self.assertRaises(ValueError):
                evidence_metrics([], gold, self.pages)

        blank = {("doc", 1): {"text": " " * 10, "removed_spans": []}}
        with self.assertRaisesRegex(ValueError, "no retained"):
            evidence_metrics([], required, blank)


class ContextPackingTests(unittest.TestCase):
    def test_over_budget_item_is_skipped_and_later_item_can_fit(self):
        big = document("big", 0, 10, text="x" * 100)
        small = document("small", 0, 2)
        budget = len(render_context([small]))
        packed = pack_context([big, small], budget, len)
        self.assertEqual([item["chunk_id"] for item in packed["documents"]], ["small"])
        self.assertEqual(packed["token_count"], budget)
        self.assertEqual(
            packed["skipped"], [{"chunk_id": "big", "reason": "token_budget"}]
        )

    def test_labels_and_separators_count_towards_budget(self):
        chunks = [document("a", 0, 5), document("b", 5, 10)]
        full_size = len(render_context(chunks))
        packed = pack_context(chunks, full_size - 1, len)
        self.assertEqual(len(packed["documents"]), 1)
        self.assertIn("pdf_page=1", packed["text"])
        self.assertEqual(pack_context(chunks, full_size, len)["token_count"], full_size)

    def test_duplicate_ids_do_not_consume_budget_twice(self):
        chunk = document("a", 0, 10)
        packed = pack_context([chunk, chunk], 1000, len)
        self.assertEqual(len(packed["documents"]), 1)
        self.assertEqual(packed["skipped"][0]["reason"], "duplicate_id")

    def test_skipped_evidence_does_not_get_credit(self):
        chunk = document("a", 0, 10)
        packed = pack_context([chunk], 1, len)
        self.assertEqual(packed["documents"], [])
        self.assertEqual(packed["token_count"], 0)
        pages = {("doc", 1): {"text": "abcdefghij", "removed_spans": []}}
        values = evidence_metrics(
            packed["documents"], [{"id": "rule", "locators": [locator()]}], pages
        )
        self.assertEqual(values["evidence_coverage"], 0)

        with self.assertRaises(ValueError):
            pack_context([chunk], 0, len)


class EvaluationDatasetTests(unittest.TestCase):
    def test_v2_gold_does_not_depend_on_chunk_ids(self):
        script = Path(__file__).resolve().parents[1] / "scripts/evaluate_retrieval.py"
        namespace = runpy.run_path(str(script))
        records = namespace["evaluation_records"](
            Path("nonexistent-chunks.jsonl"), "v2"
        )
        self.assertEqual(len(records), 142)
        self.assertEqual(
            len({row["expectations"]["scenario_id"] for row in records}), 71
        )

        for row in records:
            self.assertNotIn("relevant_chunk_ids", row["expectations"])
            self.assertTrue(row["expectations"]["required_evidence"])


if __name__ == "__main__":
    unittest.main()
