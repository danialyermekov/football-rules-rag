import copy
import hashlib
import json
import tempfile
import unittest
from itertools import pairwise
from pathlib import Path
from unittest.mock import patch

from langchain_core.documents import Document
from test_cleaning import page_record

from football_rules.ingestion.chunking import (
    ChunkConfig,
    chunk_corpus,
    chunk_page,
    source_positions,
)
from football_rules.ingestion.cleaning import clean_page
from football_rules.io import write_jsonl


def nonwhitespace(text):
    return "".join(text.split())


class ProvenanceAssertions:
    def assert_provenance(self, page, chunks):
        covered = set()

        for chunk in chunks:
            start, end = chunk["cleaned_start"], chunk["cleaned_end"]
            self.assertEqual(chunk["text"], page["cleaned_text"][start:end])
            original = "".join(
                page["text"][span["start"] : span["end"]]
                for span in chunk["source_spans"]
            )
            self.assertEqual(nonwhitespace(original), nonwhitespace(chunk["text"]))
            self.assertEqual(chunk["pdf_page"], page["pdf_page"])
            self.assertEqual(chunk["source_sha256"], page["source_sha256"])
            covered.update(range(start, end))

        substantive = {
            index
            for index, character in enumerate(page["cleaned_text"])
            if not character.isspace()
        }
        self.assertTrue(substantive.issubset(covered))


class ChunkingTests(ProvenanceAssertions, unittest.TestCase):
    def test_size_overlap_and_exact_source_ranges_with_repeated_text(self):
        page = clean_page(page_record("98\n" + "Мяч остаётся в игре. " * 30))
        chunks = chunk_page(page, ChunkConfig(65, 25))

        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(0 < len(chunk["text"]) <= 65 for chunk in chunks))
        self.assertTrue(
            any(
                left["cleaned_end"] > right["cleaned_start"]
                for left, right in pairwise(chunks)
            )
        )
        self.assert_provenance(page, chunks)
        self.assertTrue(
            all(
                span["start"] >= 3 for chunk in chunks for span in chunk["source_spans"]
            )
        )

    def test_long_word_fallback_clips_source_ranges(self):
        page = clean_page(page_record("abcdefghijklmnopqrstuvwxyz"))
        chunks = chunk_page(page, ChunkConfig(7, 2))
        self.assertEqual(chunks[0]["source_spans"], [{"start": 0, "end": 7}])
        self.assertEqual(chunks[1]["source_spans"], [{"start": 5, "end": 12}])
        self.assert_provenance(page, chunks)

    def test_multiline_nested_list_soft_hyphen_and_removed_header(self):
        page = clean_page(
            page_record(
                "98\nПроцедура\n\u2002• soft\u00ad\nware must not be\nreplaced.\n98Правила игры 2026/27 | Правило 2 | Мяч\n"
            )
        )
        chunks = chunk_page(page, ChunkConfig(25, 5))
        self.assert_provenance(page, chunks)
        self.assertNotIn("98", "".join(chunk["text"] for chunk in chunks))

    def test_empty_pages_have_no_chunks(self):
        self.assertEqual(chunk_page(clean_page(page_record("98")), ChunkConfig()), [])

    def test_configuration_and_chunk_ids_are_reproducible(self):
        page = clean_page(page_record("The ball is in play."))
        original = copy.deepcopy(page)
        first = chunk_page(page, ChunkConfig(50, 5))
        self.assertEqual(first, chunk_page(page, ChunkConfig(50, 5)))
        self.assertNotEqual(
            first[0]["chunk_id"], chunk_page(page, ChunkConfig(60, 5))[0]["chunk_id"]
        )
        self.assertEqual(page, original)
        self.assertEqual(first[0]["chunking"]["length_unit"], "unicode_characters")

    def test_invalid_configuration_is_rejected(self):
        for size, overlap in [(0, 0), (-1, 0), (5, -1), (5, 5), (5, 6)]:
            with (
                self.subTest(size=size, overlap=overlap),
                self.assertRaises(ValueError),
            ):
                ChunkConfig(size, overlap)

    def test_corrupted_cleaned_text_or_ranges_are_rejected(self):
        original = clean_page(page_record("A rule."))
        changed = copy.deepcopy(original)
        changed["cleaned_text"] = "Changed"
        with self.assertRaisesRegex(ValueError, "does not match"):
            source_positions(changed)

        for spans in [
            [{"start": -1, "end": 7}],
            [{"start": 0, "end": 100}],
            [{"start": 2, "end": 2}],
        ]:
            changed = copy.deepcopy(original)
            changed["blocks"][0]["source_spans"] = spans
            with (
                self.subTest(spans=spans),
                self.assertRaisesRegex(ValueError, "ordered"),
            ):
                source_positions(changed)

        for text in ["A rules.", "Different", "A"]:
            changed = copy.deepcopy(original)
            changed["blocks"][0]["text"] = text
            changed["cleaned_text"] = text
            with self.subTest(text=text), self.assertRaises(ValueError):
                source_positions(changed)

    def test_splitter_contract_errors_are_detected(self):
        page = clean_page(page_record("abcdef"))
        invalid = [
            Document(page_content="a", metadata={"start_index": -1}),
            Document(page_content="wrong", metadata={"start_index": 0}),
            Document(page_content="abcdef", metadata={"start_index": 0}),
            Document(page_content="", metadata={"start_index": 0}),
            Document(page_content="abc", metadata={"start_index": 0}),
        ]

        for document in invalid:
            with (
                self.subTest(document=document),
                patch(
                    "football_rules.ingestion.chunking.RecursiveCharacterTextSplitter.create_documents",
                    return_value=[document],
                ),
                self.assertRaises(ValueError),
            ):
                chunk_page(page, ChunkConfig(5, 1))


class ChunkArtifactTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.input = self.root / "pages.jsonl"
        self.output = self.root / "chunks.jsonl"
        self.page = clean_page(page_record("Мяч не вышел из игры."))
        write_jsonl(self.input, [self.page])

    def test_artifact_is_deterministic_and_pages_are_separate(self):
        other = copy.deepcopy(self.page)
        other["document_id"] = "fixture-en"
        other["language"] = "en"
        write_jsonl(self.input, [self.page, other])
        original = self.input.read_bytes()
        report = chunk_corpus(self.input, self.output, ChunkConfig())
        content = self.output.read_bytes()
        chunk_corpus(self.input, self.output, ChunkConfig())

        self.assertEqual(self.input.read_bytes(), original)
        self.assertEqual(self.output.read_bytes(), content)
        self.assertEqual(report["sha256"], hashlib.sha256(content).hexdigest())
        self.assertEqual(report["input_sha256"], hashlib.sha256(original).hexdigest())
        self.assertEqual(report["chunks_by_language"], {"ru": 1, "en": 1})
        chunks = [json.loads(line) for line in content.splitlines()]
        self.assertNotEqual(chunks[0]["chunk_id"], chunks[1]["chunk_id"])

    def test_bad_inputs_preserve_existing_output(self):
        self.output.write_bytes(b"existing output")
        original = self.input.read_bytes()
        blank = clean_page(page_record("98"))
        bad_inputs = [
            b"",
            b"{invalid}",
            original + original,
            json.dumps(blank).encode(),
        ]

        for content in bad_inputs:
            self.input.write_bytes(content)
            with self.subTest(content=content), self.assertRaises(ValueError):
                chunk_corpus(self.input, self.output, ChunkConfig())
            self.assertEqual(self.output.read_bytes(), b"existing output")

    def test_input_cannot_be_overwritten(self):
        original = self.input.read_bytes()
        with self.assertRaisesRegex(ValueError, "must differ"):
            chunk_corpus(self.input, self.input, ChunkConfig())
        self.assertEqual(self.input.read_bytes(), original)


CORPUS = Path(__file__).resolve().parents[1] / "data/processed/cleaned-pages.jsonl"


@unittest.skipUnless(CORPUS.exists(), "Local cleaned corpus is unavailable")
class LocalChunkingTests(ProvenanceAssertions, unittest.TestCase):
    def test_corpus_provenance_and_unique_ids(self):
        identities = set()

        for line in CORPUS.read_text(encoding="utf-8").splitlines():
            page = json.loads(line)
            chunks = chunk_page(page, ChunkConfig())

            with self.subTest(document=page["document_id"], page=page["pdf_page"]):
                self.assert_provenance(page, chunks)

                for chunk in chunks:
                    self.assertNotIn(chunk["chunk_id"], identities)
                    identities.add(chunk["chunk_id"])


if __name__ == "__main__":
    unittest.main()
