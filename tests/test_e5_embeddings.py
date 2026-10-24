import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from football_rules.embeddings import E5Embedder, load_embedder


class E5EmbeddingTests(unittest.TestCase):
    def setUp(self):
        self.embedder = E5Embedder.__new__(E5Embedder)
        self.embedder.model = MagicMock()
        self.embedder.max_tokens = 512
        self.embedder.batch_size = 2
        self.embedder.model.tokenizer.return_value = {"input_ids": [[1, 2, 3]]}
        self.embedder.model.encode.return_value.tolist.return_value = [[1.0, 0.0]]

    def test_query_and_document_prefixes_are_distinct_for_both_languages(self):
        for text in ["Какое правило применяется?", "Which law applies?"]:
            for encode, prefix in [
                (self.embedder.encode, "passage: "),
                (self.embedder.encode_queries, "query: "),
            ]:
                with self.subTest(text=text, prefix=prefix):
                    self.embedder.model.reset_mock()
                    self.assertEqual(encode([text]), [[1.0, 0.0]])
                    prepared = [prefix + text]
                    self.embedder.model.tokenizer.assert_called_once_with(
                        prepared, padding=False, truncation=False
                    )
                    call = self.embedder.model.encode.call_args
                    self.assertEqual(call.args, (prepared,))
                    self.assertEqual(call.kwargs["prompt"], "")
                    self.assertTrue(call.kwargs["normalize_embeddings"])

    def test_empty_input_is_rejected_before_adding_prefix(self):
        for encode in [self.embedder.encode, self.embedder.encode_queries]:
            for texts in [[], [" "], ["ball", ""]]:
                with self.subTest(texts=texts), self.assertRaises(ValueError):
                    encode(texts)
        self.embedder.model.encode.assert_not_called()

    def test_512_token_boundary_includes_prefix_and_special_tokens(self):
        for encode in [self.embedder.encode, self.embedder.encode_queries]:
            self.embedder.model.reset_mock()
            self.embedder.model.tokenizer.return_value = {"input_ids": [[1] * 513]}
            with self.assertRaisesRegex(ValueError, "including prompt"):
                encode(["ball"])
            self.embedder.model.encode.assert_not_called()

            self.embedder.model.tokenizer.return_value = {"input_ids": [[1] * 512]}
            self.assertEqual(encode(["ball"]), [[1.0, 0.0]])

    def test_unpinned_files_are_rejected_before_loading_weights(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            self.assertRaisesRegex(ValueError, "pinned revision"),
        ):
            E5Embedder(Path(directory))

    def test_factory_selects_e5_without_loading_other_models(self):
        with patch("football_rules.embeddings.E5Embedder") as model:
            self.assertIs(load_embedder("multilingual-e5-large"), model.return_value)
