import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from football_rules.embeddings import (
    QWEN_QUERY_PROMPT,
    BGEEmbedder,
    QwenEmbedder,
    load_embedder,
)


class QwenEmbeddingTests(unittest.TestCase):
    def setUp(self):
        self.embedder = QwenEmbedder.__new__(QwenEmbedder)
        self.embedder.model = MagicMock()
        self.embedder.max_tokens = 100
        self.embedder.batch_size = 2
        self.embedder.model.tokenizer.return_value = {"input_ids": [[1, 2]]}
        self.embedder.model.encode.return_value.tolist.return_value = [[1.0, 0.0]]

    def test_only_queries_receive_instruction_and_it_is_applied_once(self):
        query = "Можно ли оказаться вне игры после вбрасывания?"
        self.embedder.encode_queries([query])
        prepared = [QWEN_QUERY_PROMPT + query]
        self.embedder.model.tokenizer.assert_called_once_with(
            prepared, padding=False, truncation=False
        )
        self.assertEqual(self.embedder.model.encode.call_args.args, (prepared,))
        self.assertEqual(self.embedder.model.encode.call_args.kwargs["prompt"], "")
        self.assertTrue(
            self.embedder.model.encode.call_args.kwargs["normalize_embeddings"]
        )

        self.embedder.model.reset_mock()
        self.embedder.encode(["A player cannot be offside directly from a throw-in."])
        encoded = self.embedder.model.encode.call_args.args[0]
        self.assertFalse(encoded[0].startswith("Instruct:"))

    def test_empty_queries_and_documents_fail_before_instruction_is_added(self):
        for encode in (self.embedder.encode, self.embedder.encode_queries):
            for texts in ([], [""], [" \n"], ["ball", " "]):
                with (
                    self.subTest(encode=encode.__name__, texts=texts),
                    self.assertRaisesRegex(ValueError, "nonempty"),
                ):
                    encode(texts)

        self.embedder.model.encode.assert_not_called()

    def test_token_limit_includes_query_instruction(self):
        self.embedder.max_tokens = 3
        self.embedder.model.tokenizer.return_value = {"input_ids": [[1, 2, 3, 4]]}
        with self.assertRaisesRegex(ValueError, "including prompt"):
            self.embedder.encode_queries(["ball"])
        self.embedder.model.encode.assert_not_called()

        self.embedder.model.tokenizer.return_value = {"input_ids": [[1, 2, 3]]}
        self.assertEqual(self.embedder.encode_queries(["ball"]), [[1.0, 0.0]])

    def test_unpinned_files_are_rejected_before_loading_weights(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            self.assertRaisesRegex(ValueError, "pinned revision"),
        ):
            QwenEmbedder(Path(directory))

    def test_factory_keeps_bge_as_separate_implementation(self):
        with patch("football_rules.embeddings.BGEEmbedder") as bge:
            self.assertIs(load_embedder("bge-m3"), bge.return_value)
        with patch("football_rules.embeddings.QwenEmbedder") as qwen:
            self.assertIs(load_embedder("qwen3-0.6b"), qwen.return_value)
        with self.assertRaisesRegex(ValueError, "Unknown"):
            load_embedder("unknown")

    def test_bge_queries_remain_identical_to_document_encoding(self):
        bge = BGEEmbedder.__new__(BGEEmbedder)
        with patch.object(bge, "encode", return_value=[[1.0, 0.0]]) as encode:
            self.assertEqual(bge.encode_queries(["ball"]), [[1.0, 0.0]])
            encode.assert_called_once_with(["ball"])
