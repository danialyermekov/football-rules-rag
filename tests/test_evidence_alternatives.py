import unittest

from football_rules.evidence_alternatives import alternative_evidence_metrics

from football_rules.evidence_evaluation import evidence_metrics


def unit(page):
    return [
        {
            "id": "rule",
            "locators": [
                {
                    "document_id": "doc",
                    "pdf_page": page,
                    "char_start": 0,
                    "char_end": 10,
                }
            ],
        }
    ]


def doc(page, start=0, end=10):
    return {
        "document_id": "doc",
        "pdf_page": page,
        "source_spans": [{"start": start, "end": end}],
    }


class AlternativeEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.pages = {
            ("doc", i): {"text": "abcdefghij", "removed_spans": []} for i in (1, 2)
        }

    def score(self, documents, alternatives):
        return alternative_evidence_metrics(
            documents, unit(1), alternatives, self.pages
        )

    def test_canonical_success(self):
        values = self.score([doc(1)], [unit(2)])
        self.assertEqual(values["canonical_complete_evidence"], 1)
        self.assertEqual(values["alternative_complete_evidence"], 1)

    def test_alternative_success(self):
        values = self.score([doc(2)], [unit(2)])
        self.assertEqual(values["canonical_complete_evidence"], 0)
        self.assertEqual(values["alternative_complete_evidence"], 1)
        self.assertEqual(values["alternative_strict_complete_evidence"], 1)

    def test_no_alternatives_matches_v2(self):
        for documents in ([], [doc(1)], [doc(1, end=8)], [doc(2)]):
            base = evidence_metrics(documents, unit(1), self.pages)
            actual = self.score(documents, [])
            for key in ("complete_evidence", "strict_complete_evidence"):
                self.assertEqual(actual[f"canonical_{key}"], base[key])
                self.assertEqual(actual[f"alternative_{key}"], base[key])

    def test_cannot_stitch_half_options(self):
        values = self.score([doc(1, end=5), doc(2, start=5)], [unit(2)])
        self.assertEqual(values["alternative_complete_evidence"], 0)

    def test_all_units_and_locators_required_in_each_option(self):
        for option in (
            unit(1) + unit(2),
            [
                {
                    "id": "both",
                    "locators": unit(1)[0]["locators"] + unit(2)[0]["locators"],
                }
            ],
        ):
            values = self.score([doc(2)], [option])
            self.assertEqual(values["alternative_complete_evidence"], 0)

    def test_threshold_not_strict(self):
        values = self.score([doc(2, end=8)], [unit(2)])
        self.assertEqual(values["alternative_complete_evidence"], 1)
        self.assertEqual(values["alternative_strict_complete_evidence"], 0)

    def test_validate_all_options_even_when_canonical_passes(self):
        bad_range = unit(2)
        bad_range[0]["locators"][0]["char_end"] = 11
        for invalid in ([], [{"id": "empty", "locators": []}], bad_range):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                self.score([doc(1)], [unit(2), invalid])


if __name__ == "__main__":
    unittest.main()
