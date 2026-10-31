import copy
import unittest

from football_rules.context_compaction import pack_overlap_context


def page(text="abcdefghij", number=1):
    return {
        "document_id": "doc",
        "pdf_page": number,
        "printed_page": number,
        "edition": "example",
        "language": "en",
        "publisher": "example",
        "source_url": "https://example.invalid/rules",
        "source_sha256": "source",
        "cleaning_version": "example",
        "cleaning_flags": [],
        "text": text,
        "cleaned_text": text,
        "removed_spans": [],
        "blocks": [{"text": text, "source_spans": [{"start": 0, "end": len(text)}]}],
    }


def chunk(source, identity, start, end, spans=None):
    return {
        **{
            k: source[k]
            for k in (
                "document_id",
                "pdf_page",
                "printed_page",
                "edition",
                "language",
                "publisher",
                "source_url",
                "source_sha256",
                "cleaning_version",
                "cleaning_flags",
            )
        },
        "chunk_id": identity,
        "text": source["cleaned_text"][start:end],
        "cleaned_start": start,
        "cleaned_end": end,
        "source_spans": spans or [{"start": start, "end": end}],
    }


class OverlapPackingTests(unittest.TestCase):
    def setUp(self):
        self.source = page()
        self.pages = {("doc", 1): self.source, ("doc", 2): page(number=2)}

    def tokens(self, text):
        return len(text.split())

    def test_overlap_admits_whole_originals_with_one_exact_source_union(self):
        docs = [chunk(self.source, "a", 0, 6), chunk(self.source, "b", 4, 10)]
        before = copy.deepcopy(docs)
        result = pack_overlap_context(docs, self.pages, 4, self.tokens)
        self.assertEqual(result["selected_documents"], docs)
        self.assertEqual(docs, before)
        self.assertEqual(len(result["documents"]), 1)
        block = result["documents"][0]
        self.assertEqual(block["text"], "abcdefghij")
        self.assertEqual(block["source_spans"], [{"start": 0, "end": 10}])
        self.assertEqual(block["constituent_chunk_ids"], ["a", "b"])
        self.assertNotIn(block["chunk_id"], {"a", "b"})
        self.assertEqual(result["token_count"], 4)
        self.assertEqual(result["skipped"], [])

    def test_touching_disjoint_and_cross_page_chunks_remain_separate(self):
        docs = [
            chunk(self.source, "a", 0, 3),
            chunk(self.source, "b", 3, 6),
            chunk(self.source, "c", 8, 10),
            chunk(self.pages["doc", 2], "d", 0, 4),
        ]
        result = pack_overlap_context(docs, self.pages, 100, self.tokens)
        self.assertEqual(result["documents"], docs)
        self.assertNotIn("gh", result["documents"][1]["text"])

    def test_transitive_component_keeps_earliest_admission_position(self):
        other = chunk(self.pages["doc", 2], "other", 0, 2)
        docs = [
            chunk(self.source, "a", 4, 8),
            other,
            chunk(self.source, "c", 0, 5),
            chunk(self.source, "d", 7, 10),
        ]
        result = pack_overlap_context(docs, self.pages, 100, self.tokens)
        self.assertEqual(result["selected_documents"], docs)
        self.assertEqual(len(result["documents"]), 2)
        self.assertEqual(result["documents"][0]["text"], "abcdefghij")
        self.assertEqual(
            result["documents"][0]["constituent_chunk_ids"], ["a", "c", "d"]
        )
        self.assertEqual(result["documents"][1], other)

    def test_new_bridge_can_merge_two_previously_separate_components(self):
        docs = [
            chunk(self.source, "a", 0, 3),
            chunk(self.source, "b", 3, 6),
            chunk(self.source, "bridge", 2, 4),
        ]
        result = pack_overlap_context(docs, self.pages, 100, self.tokens)
        self.assertEqual(len(result["documents"]), 1)
        self.assertEqual(result["documents"][0]["text"], "abcdef")
        self.assertEqual(result["selected_documents"], docs)

    def test_source_ranges_do_not_restore_removed_text(self):
        source = page("abXXcdef")
        source["cleaned_text"] = "ab\n\ncdef"
        source["removed_spans"] = [{"start": 2, "end": 4}]
        source["blocks"] = [
            {"text": "ab", "source_spans": [{"start": 0, "end": 2}]},
            {"text": "cdef", "source_spans": [{"start": 4, "end": 8}]},
        ]
        docs = [
            chunk(source, "a", 0, 6, [{"start": 0, "end": 2}, {"start": 4, "end": 6}]),
            chunk(source, "b", 4, 8),
        ]
        result = pack_overlap_context(docs, {("doc", 1): source}, 100, self.tokens)
        block = result["documents"][0]
        self.assertEqual(block["text"], "ab\n\ncdef")
        self.assertEqual(
            block["source_spans"], [{"start": 0, "end": 2}, {"start": 4, "end": 8}]
        )
        self.assertNotIn("XX", block["text"])

    def test_exact_trial_tokenization_can_reject_a_merge_without_eviction(self):
        def tokens(text):
            return 9 if "abcdefghij" in text else 4

        docs = [chunk(self.source, "a", 0, 6), chunk(self.source, "b", 4, 10)]
        result = pack_overlap_context(docs, self.pages, 4, tokens)
        self.assertEqual(result["documents"], [docs[0]])
        self.assertEqual(result["selected_documents"], [docs[0]])
        self.assertEqual(
            result["skipped"], [{"chunk_id": "b", "reason": "token_budget"}]
        )

    def test_invalid_provenance_duplicate_ids_and_budget_are_rejected(self):
        valid = chunk(self.source, "a", 0, 6)
        for field, value in [
            ("text", "wrong"),
            ("source_spans", [{"start": 1, "end": 6}]),
            ("language", "ru"),
            ("cleaned_end", 99),
        ]:
            with self.subTest(field=field), self.assertRaises(ValueError):
                pack_overlap_context(
                    [{**valid, field: value}], self.pages, 100, self.tokens
                )
        with self.assertRaises(ValueError):
            pack_overlap_context([valid, valid], self.pages, 100, self.tokens)
        with self.assertRaises(ValueError):
            pack_overlap_context([], self.pages, 0, self.tokens)
        self.assertEqual(
            pack_overlap_context([], self.pages, 4, self.tokens)["text"], ""
        )


if __name__ == "__main__":
    unittest.main()
