import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from football_rules.cleaning import clean_corpus, clean_page
from football_rules.ingestion import PageRecord
from football_rules.jsonl import write_jsonl


def page_record(raw_text: str, printed_page: int | None = 98) -> PageRecord:
    return {
        "document_id": "fixture-ru",
        "edition": "2026/27",
        "language": "ru",
        "publisher": "Test",
        "source_url": "https://example.com/rules.pdf",
        "source_sha256": "a" * 64,
        "pdf_page": 100,
        "printed_page": printed_page,
        "printed_page_method": "footer_heuristic",
        "raw_text": raw_text,
        "text": " ".join(raw_text.split()),
        "raster_image_count": 0,
        "flags": [],
        "extractor": "fixture",
    }


class CleaningTests(unittest.TestCase):
    def test_removes_only_recognized_noise_and_preserves_original_fields(self):
        source = page_record(
            "98\nНельзя назначить пенальти.\n11\n"
            "Ссылка: Правила игры 2026/27.\n"
            "98Правила игры 2026/27 | Правило 8 | Начало игры\n"
        )
        cleaned = clean_page(source)

        for key, value in source.items():
            self.assertEqual(cleaned[key], value)

        self.assertEqual(
            [span["reason"] for span in cleaned["removed_spans"]],
            ["printed_page_number", "running_header"],
        )
        self.assertIn("Нельзя назначить пенальти.", cleaned["cleaned_text"])
        self.assertIn("11", cleaned["cleaned_text"])
        self.assertIn("Ссылка: Правила игры 2026/27.", cleaned["cleaned_text"])

    def test_english_header_and_footer_number(self):
        source = page_record(
            "L aws of the Game 2026/2 7 | Law 1 | The Field of Play\n"
            "The ball must not be replaced\nwithout permission.\n98"
        )
        cleaned = clean_page(source)
        self.assertEqual(
            cleaned["cleaned_text"], "The ball must not be replaced without permission."
        )
        self.assertEqual(len(cleaned["removed_spans"]), 2)

    def test_headings_wrapping_and_nested_bullets(self):
        source = page_record(
            "2. «Спорный» мяч\nПроцедура\n"
            "•\u2002Если во время\nостановки игры:\n"
            "\u2002• мяч был в пределах\nштрафной площади\n"
            "•\u2002Все остальные игроки\nдолжны отойти\n"
            "Мяч в игре, когда он касается земли."
        )
        blocks = clean_page(source)["blocks"]

        self.assertEqual(
            [block["kind"] for block in blocks],
            ["heading", "heading", "list_item", "list_item", "list_item", "text"],
        )
        self.assertEqual(blocks[2]["text"], "• Если во время остановки игры:")
        self.assertEqual(blocks[3]["list_level"], 1)
        self.assertEqual(blocks[3]["text"], "  • мяч был в пределах штрафной площади")
        self.assertEqual(blocks[-1]["text"], "Мяч в игре, когда он касается земли.")

    def test_source_ranges_cover_every_nonwhitespace_character(self):
        source = page_record("\n98\n\n•\u2002Мяч  должен\n\tкоснуться земли.\n\n11\n")
        cleaned = clean_page(source)
        spans = list(cleaned["removed_spans"])

        for block in cleaned["blocks"]:
            spans.extend(block["source_spans"])

        covered = set()

        for span in spans:
            covered.update(range(span["start"], span["end"]))

        for index, character in enumerate(source["text"]):
            if not character.isspace():
                self.assertIn(index, covered)

        first = cleaned["blocks"][0]["source_spans"][0]
        self.assertEqual(source["text"][first["start"] : first["end"]], "• Мяч должен")

    def test_hyphens_and_uncertain_word_spacing(self):
        source = page_record(
            "non-kicking\nplayer; недисциплиниро ванного\ninter-\nnational\nsoft\u00ad\nware"
        )
        cleaned = clean_page(source)
        self.assertIn("non-kicking player", cleaned["cleaned_text"])
        self.assertIn("недисциплиниро ванного", cleaned["cleaned_text"])
        self.assertIn("inter- national", cleaned["cleaned_text"])
        self.assertIn("software", cleaned["cleaned_text"])
        self.assertIn("unresolved_line_hyphen", cleaned["cleaning_flags"])

    def test_quoted_paragraph_is_separate_from_known_heading(self):
        blocks = clean_page(
            page_record(
                "Нарушения и наказания\n«Спорный» мяч разыгрывается снова, если:"
            )
        )["blocks"]
        self.assertEqual(len(blocks), 2)
        self.assertEqual(blocks[0]["kind"], "heading")
        self.assertEqual(blocks[1]["kind"], "text")

        separated = clean_page(page_record("Процедура\n\nМяч касается земли."))
        self.assertEqual(len(separated["blocks"]), 2)

    def test_tables_keep_line_order_and_get_review_flag(self):
        source = page_record("Сводная таблица\nНарушение\nРешение\nРука\nШтрафной удар")
        source["raster_image_count"] = 1
        cleaned = clean_page(source)
        self.assertEqual(cleaned["cleaned_text"], source["raw_text"])
        self.assertEqual(cleaned["blocks"][0]["kind"], "unstructured")
        self.assertIn("table_layout_not_reconstructed", cleaned["cleaning_flags"])
        self.assertIn("raster_images_not_interpreted", cleaned["cleaning_flags"])

    def test_empty_page_and_unknown_printed_page(self):
        cleaned = clean_page(page_record("", None))
        self.assertEqual(cleaned["blocks"], [])
        self.assertEqual(cleaned["cleaned_text"], "")
        self.assertIn("sparse_text_review", cleaned["cleaning_flags"])
        self.assertEqual(clean_page(page_record("11", None))["cleaned_text"], "11")

    def test_inconsistent_source_is_rejected(self):
        source = page_record("Do not change this.")
        source["text"] = "Changed"
        with self.assertRaisesRegex(ValueError, "inconsistent"):
            clean_page(source)


class CleaningArtifactTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / "pages.jsonl"
        self.output = self.root / "cleaned.jsonl"
        write_jsonl(self.source, [page_record("98\nМяч в игре.")])

    def test_corpus_is_deterministic_and_source_unchanged(self):
        original = self.source.read_bytes()
        report = clean_corpus(self.source, self.output)
        result = self.output.read_bytes()
        clean_corpus(self.source, self.output)

        self.assertEqual(self.source.read_bytes(), original)
        self.assertEqual(self.output.read_bytes(), result)
        self.assertEqual(report["sha256"], hashlib.sha256(result).hexdigest())
        self.assertEqual(report["pages"], 1)
        self.assertEqual(report["removed"], {"printed_page_number": 1})
        self.assertEqual(json.loads(result)["cleaned_text"], "Мяч в игре.")

    def test_bad_inputs_preserve_existing_output(self):
        self.output.write_bytes(b"existing output")
        original = self.source.read_bytes()
        bad_inputs = [b"", original + original, b"{invalid json}"]

        for content in bad_inputs:
            with self.subTest(content=content):
                self.source.write_bytes(content)
                with self.assertRaises(ValueError):
                    clean_corpus(self.source, self.output)
                self.assertEqual(self.output.read_bytes(), b"existing output")

    def test_cannot_overwrite_source(self):
        original = self.source.read_bytes()
        with self.assertRaisesRegex(ValueError, "must differ"):
            clean_corpus(self.source, self.source)
        self.assertEqual(self.source.read_bytes(), original)

    def test_failed_atomic_replace_preserves_output_and_cleans_temporary(self):
        self.output.write_bytes(b"existing output")
        with (
            patch(
                "football_rules.jsonl.os.replace",
                side_effect=OSError("fixture failure"),
            ),
            self.assertRaisesRegex(OSError, "fixture failure"),
        ):
            clean_corpus(self.source, self.output)

        self.assertEqual(self.output.read_bytes(), b"existing output")
        self.assertEqual(list(self.root.glob("*.tmp")), [])


CORPUS = Path(__file__).resolve().parents[1] / "data/processed/pages.jsonl"


@unittest.skipUnless(CORPUS.exists(), "Local ingestion artifact is unavailable")
class LocalCleaningTests(unittest.TestCase):
    def test_all_pages_preserve_source_and_account_for_every_character(self):
        for line in CORPUS.read_text(encoding="utf-8").splitlines():
            source = json.loads(line)
            cleaned = clean_page(source)

            with self.subTest(document=source["document_id"], page=source["pdf_page"]):
                for key, value in source.items():
                    self.assertEqual(cleaned[key], value)

                spans = list(cleaned["removed_spans"])

                for block in cleaned["blocks"]:
                    passages = [
                        source["text"][span["start"] : span["end"]]
                        for span in block["source_spans"]
                    ]
                    expected = " ".join(" ".join(passages).split()).replace(
                        "\u00ad ", ""
                    )
                    actual = " ".join(block["text"].split())
                    self.assertEqual(actual, expected)
                    spans.extend(block["source_spans"])

                covered = set()

                for span in spans:
                    covered.update(range(span["start"], span["end"]))

                substantive = {
                    index
                    for index, character in enumerate(source["text"])
                    if not character.isspace()
                }
                self.assertTrue(substantive.issubset(covered))


if __name__ == "__main__":
    unittest.main()
