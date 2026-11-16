import hashlib
import json
import tempfile
import unittest
from dataclasses import asdict, replace
from pathlib import Path

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from football_rules.ingestion.pdf import (
    SourceDocument,
    extract_document,
    ingest,
    load_sources,
)


class IngestionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.pdf_path = self.root / "source.pdf"
        writer = PdfWriter()
        page = writer.add_blank_page(width=200, height=300)
        page[NameObject("/Resources")] = DictionaryObject(
            {
                NameObject("/Font"): DictionaryObject(
                    {
                        NameObject("/F1"): DictionaryObject(
                            {
                                NameObject("/Type"): NameObject("/Font"),
                                NameObject("/Subtype"): NameObject("/Type1"),
                                NameObject("/BaseFont"): NameObject("/Helvetica"),
                            }
                        ),
                    }
                ),
            }
        )
        content = DecodedStreamObject()
        content.set_data(
            b"BT /F1 12 Tf 20 200 Td (A rule with) Tj 0 -20 Td (a second line.) Tj ET "
            b"BT /F1 12 Tf 20 100 Td (7) Tj ET "
            b"BT /F1 8 Tf 100 15 Td (7) Tj ET "
            b"BT /F1 8 Tf 175 15 Td (42) Tj ET"
        )
        page[NameObject("/Contents")] = content
        writer.add_blank_page(width=200, height=300)
        writer.write(self.pdf_path)
        self.source = SourceDocument(
            id="fixture-en",
            edition="test",
            language="en",
            publisher="Тестовый источник",
            source_url="https://example.com/source.pdf",
            local_path="source.pdf",
            sha256=hashlib.sha256(self.pdf_path.read_bytes()).hexdigest(),
            bytes=self.pdf_path.stat().st_size,
            pdf_pages=2,
        )
        self.manifest = self.root / "sources.json"
        self.manifest.write_text(json.dumps([asdict(self.source)]), encoding="utf-8")

    def test_extraction_preserves_text_and_blank_page(self):
        pages = extract_document(self.source, self.root)
        self.assertEqual(len(pages), 2)
        self.assertIn("A rule with\na second line.", pages[0]["raw_text"])
        self.assertIn("A rule with a second line.", pages[0]["text"])
        self.assertEqual(pages[0]["printed_page"], 42)
        self.assertEqual(pages[0]["pdf_page"], 1)
        self.assertEqual(pages[0]["source_sha256"], self.source.sha256)
        self.assertEqual(pages[1]["text"], "")
        self.assertIn("no_text", pages[1]["flags"])
        self.assertIsNone(pages[1]["printed_page"])

    def test_ambiguous_footer_is_not_guessed(self):
        writer = PdfWriter(clone_from=self.pdf_path)
        page = writer.pages[0]
        content = DecodedStreamObject()
        content.set_data(
            page.get_contents().get_data() + b" BT /F1 8 Tf 20 15 Td (43) Tj ET"
        )
        page[NameObject("/Contents")] = content
        writer.write(self.pdf_path)
        source = replace(
            self.source,
            bytes=self.pdf_path.stat().st_size,
            sha256=hashlib.sha256(self.pdf_path.read_bytes()).hexdigest(),
        )
        pages = extract_document(source, self.root)
        self.assertIsNone(pages[0]["printed_page"])
        self.assertIn("printed_page_ambiguous", pages[0]["flags"])

    def test_source_mismatch_preserves_existing_output(self):
        output = self.root / "pages.jsonl"
        output.write_bytes(b"existing output\n")
        self.pdf_path.write_bytes(self.pdf_path.read_bytes() + b"changed")
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            ingest(self.manifest, output, self.root)
        self.assertEqual(output.read_bytes(), b"existing output\n")

    def test_page_count_mismatch_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "page count"):
            extract_document(replace(self.source, pdf_pages=3), self.root)

    def test_manifest_validation_rejects_invalid_counts_and_duplicate_ids(self):
        for entries in (
            [asdict(replace(self.source, pdf_pages=True))],
            [asdict(self.source), asdict(self.source)],
        ):
            with self.subTest(entries=entries):
                self.manifest.write_text(json.dumps(entries), encoding="utf-8")
                with self.assertRaises(ValueError):
                    load_sources(self.manifest)

    def test_output_cannot_overwrite_source_or_manifest(self):
        for output in (self.pdf_path, self.manifest):
            with (
                self.subTest(output=output),
                self.assertRaisesRegex(ValueError, "overwrite"),
            ):
                ingest(self.manifest, output, self.root)

    def test_source_cannot_escape_root(self):
        with self.assertRaisesRegex(ValueError, "source root"):
            extract_document(
                replace(self.source, local_path="../outside.pdf"), self.root
            )

    def test_ingestion_writes_deterministic_utf8_jsonl(self):
        output = self.root / "processed" / "pages.jsonl"
        report = ingest(self.manifest, output, self.root)
        first = output.read_bytes()
        again = ingest(self.manifest, output, self.root)
        self.assertEqual(first, output.read_bytes())
        self.assertNotIn(b"\r\n", first)
        self.assertIn("Тестовый источник".encode(), first)
        self.assertEqual(report, again)
        self.assertEqual(report["sha256"], hashlib.sha256(first).hexdigest())
        self.assertEqual(len(first.splitlines()), 2)


ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(
    (ROOT / "data/processed/pages.jsonl").exists()
    and (ROOT / "data/processed/reference-pages.json").exists(),
    "Local extracted corpus and reference snapshot are required",
)
class LocalCorpusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.records = [
            json.loads(line)
            for line in (ROOT / "data/processed/pages.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
        ]
        cls.index = {
            (page["document_id"], page["pdf_page"]): page for page in cls.records
        }

    def test_all_pages_preserve_reference_text_and_source_metadata(self):
        snapshot = json.loads(
            (ROOT / "data/processed/reference-pages.json").read_text(encoding="utf-8")
        )
        sources = load_sources(ROOT / "docs/source-manifest.json")
        self.assertEqual(len(self.records), sum(source.pdf_pages for source in sources))
        self.assertEqual(len(self.index), len(self.records))
        for source in sources:
            for number in range(1, source.pdf_pages + 1):
                page = self.index[source.id, number]
                self.assertEqual(page["text"], snapshot[source.language][number - 1])
                self.assertEqual(page["text"], " ".join(page["raw_text"].split()))
                self.assertEqual(page["source_sha256"], source.sha256)
                self.assertEqual(page["edition"], source.edition)
                self.assertEqual(page["language"], source.language)

    def test_dev_evidence_spans_and_printed_pages_are_preserved(self):
        scenarios = [
            json.loads(line)
            for line in (ROOT / "data/evaluation/scenarios.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
        ]
        required = {
            key
            for row in scenarios
            if row["split"] == "dev"
            for key in row["required_evidence"]
        }
        evidence = [
            json.loads(line)
            for line in (ROOT / "data/evaluation/evidence.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
        ]
        for item in evidence:
            if item["id"] not in required:
                continue
            for spans in item["locators"].values():
                for span in spans:
                    page = self.index[span["document_id"], span["pdf_page"]]
                    passage = page["text"][span["char_start"] : span["char_end"]]
                    self.assertEqual(
                        hashlib.sha256(passage.encode("utf-8")).hexdigest(),
                        span["span_sha256"],
                        item["id"],
                    )
                    self.assertEqual(page["printed_page"], span["printed_page"])


if __name__ == "__main__":
    unittest.main()
