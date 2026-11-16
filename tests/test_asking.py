import io
import json
import os
import sys
from tempfile import TemporaryDirectory
import unittest
from contextlib import ExitStack, redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from google.genai import types

from football_rules import main
from football_rules.app.chat import ask_question


class AskingTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.dict(os.environ, {"GEMINI_API_KEY": "test"}))
        self.stack.enter_context(patch("football_rules.app.chat.load_dotenv"))
        self.stack.enter_context(patch("football_rules.app.chat.configure_tracking"))
        self.stack.enter_context(
            patch(
                "football_rules.app.chat.resolve_collection",
                side_effect=lambda _db, col, _model: col or "resolved_collection",
            )
        )
        self.embedder_loader = self.stack.enter_context(
            patch("football_rules.app.chat.load_embedder")
        )
        self.embedder_loader.return_value.count_tokens.return_value = 2
        self.bm25_cls = self.stack.enter_context(
            patch("football_rules.app.chat.BM25Retriever")
        )
        self.reranker_cls = self.stack.enter_context(
            patch("football_rules.app.chat.CrossEncoderReranker")
        )
        self.dense_cls = self.stack.enter_context(
            patch("football_rules.app.chat.DenseRetriever")
        )
        self.dense = self.dense_cls.return_value
        self.hybrid_cls = self.stack.enter_context(
            patch("football_rules.app.chat.HybridRetriever")
        )
        self.hybrid = self.hybrid_cls.return_value
        self.documents = [
            {
                "chunk_id": "a",
                "document_id": "ifab-en",
                "pdf_page": 10,
                "text": "The whole ball must cross the line.",
                "printed_page": "8",
            }
        ]
        self.hybrid.search.return_value = self.documents
        self.client = self.stack.enter_context(
            patch("football_rules.app.chat.genai.Client")
        )
        self.generate = self.stack.enter_context(
            patch("football_rules.app.chat.generate_answer")
        )
        self.generate.side_effect = lambda *a, **kw: {
            "answer": "Yes.",
            "status": "answered",
            "citations": ["ifab-en:10"],
            "model_version": kw["model"],
        }

    def test_retrieves_and_packs_sources_with_each_model_recipe(self):
        for model, limit in [
            ("gemini-2.5-flash-lite", None),
            ("gemini-3.8-flash", 2048),
            ("gemini-4-argon", 32768),
        ]:
            with self.subTest(model=model):
                result = ask_question("Out?", "en", model, Path("db"), "collection")
                self.hybrid.search.assert_called_with("Out?", "en", 50)
                args, kwargs = self.generate.call_args
                self.assertIn("The whole ball must cross the line.", args[3])
                self.assertEqual(kwargs["model"], model)
                self.assertEqual(kwargs.get("max_output_tokens"), limit)
                if limit:
                    self.assertEqual(kwargs["thinking_level"], types.ThinkingLevel.LOW)
                if model == "gemini-4-argon":
                    self.assertIsNone(kwargs["temperature"])
                self.assertEqual(result["documents"], self.documents)
                self.assertTrue(result["citations_valid"])
                self.dense.close.assert_called()

    def test_closes_database_on_retrieval_failure_and_does_not_call_api(self):
        self.hybrid.search.side_effect = RuntimeError("retrieval failed")
        with self.assertRaisesRegex(RuntimeError, "retrieval failed"):
            ask_question(
                "Out?", "en", "gemini-2.5-flash-lite", Path("db"), "collection"
            )
        self.dense.close.assert_called_once()
        self.client.assert_not_called()

    def test_cli_passes_question_language_model_and_returns_json(self):
        output = io.StringIO()
        with (
            patch.object(
                sys,
                "argv",
                [
                    "football-rules",
                    "ask",
                    "Out?",
                    "--language",
                    "en",
                    "--model",
                    "gemini-3.8-flash",
                    "--json",
                ],
            ),
            redirect_stdout(output),
        ):
            main()
        self.assertEqual(
            json.loads(output.getvalue())["model_version"], "gemini-3.8-flash"
        )
        self.assertEqual(self.generate.call_args.args[1:3], ("Out?", "en"))

    def test_missing_key_fails_before_loading_models_or_calling_api(self):
        with (
            patch.dict(os.environ, {}, clear=True),
            self.assertRaisesRegex(ValueError, "Configure GEMINI_API_KEY"),
        ):
            ask_question(
                "Out?", "en", "gemini-2.5-flash-lite", Path("db"), "collection"
            )
        self.hybrid.search.assert_not_called()
        self.client.assert_not_called()

    def test_cli_prints_answer_status_and_sources_by_default(self):
        output = io.StringIO()
        with (
            patch.object(sys, "argv", ["football-rules", "ask", "Мяч вышел?"]),
            redirect_stdout(output),
        ):
            main()
        self.assertIn("Yes.", output.getvalue())
        self.assertIn("Status: answered", output.getvalue())
        self.assertIn("ifab-en:10", output.getvalue())
        self.assertEqual(self.generate.call_args.args[1:3], ("Мяч вышел?", "ru"))
        self.assertEqual(
            self.generate.call_args.kwargs["model"], "gemini-2.5-flash-lite"
        )

    def test_ask_cli_supports_showing_sources_and_saving_record(self):
        with TemporaryDirectory() as tmp:
            save_file = Path(tmp) / "saved.jsonl"
            output = io.StringIO()
            with (
                patch.object(
                    sys,
                    "argv",
                    [
                        "football-rules",
                        "ask",
                        "Out?",
                        "--language",
                        "en",
                        "--sources",
                        "--save",
                        str(save_file),
                    ],
                ),
                redirect_stdout(output),
            ):
                main()
            rendered = output.getvalue()
            self.assertIn("[1] ifab-en:10 (printed_page=8, chunk_id=a) [cited]", rendered)
            self.assertIn("The whole ball must cross the line.", rendered)
            with save_file.open(encoding="utf-8") as handle:
                lines = handle.read().splitlines()
            self.assertEqual(len(lines), 1)
            saved = json.loads(lines[0])
            self.assertEqual(saved["question"], "Out?")
            self.assertEqual(saved["documents"], self.documents)
            self.assertIn("The whole ball must cross the line.", saved["context"])
            self.assertEqual(saved["settings"]["embedding"], "qwen3-0.6b")

    def test_chat_cli_loads_index_once_and_handles_sources_save_and_switches(self):
        with TemporaryDirectory() as tmp:
            save_file = Path(tmp) / "chat-saved.jsonl"
            output = io.StringIO()
            inputs = iter(
                [
                    "/sources",
                    "Первый вопрос?",
                    "/sources",
                    "/save Неверный вывод по автоголу",
                    "/model gemini-3.8-flash",
                    "/lang en",
                    "Second question?",
                    "/exit",
                ]
            )
            with (
                patch.object(
                    sys,
                    "argv",
                    [
                        "football-rules",
                        "chat",
                        "--model",
                        "gemini-4-argon",
                        "--save-path",
                        str(save_file),
                    ],
                ),
                patch("builtins.input", side_effect=lambda _prompt="": next(inputs)),
                redirect_stdout(output),
            ):
                main()

            self.embedder_loader.assert_called_once_with("qwen3-0.6b")
            self.bm25_cls.assert_called_once()
            self.dense_cls.assert_called_once()
            self.hybrid_cls.assert_called_once()
            self.dense.close.assert_called_once()
            self.assertEqual(self.generate.call_count, 2)

            first_call, second_call = self.generate.call_args_list
            self.assertEqual(first_call.args[1:3], ("Первый вопрос?", "ru"))
            self.assertEqual(first_call.kwargs["model"], "gemini-4-argon")
            self.assertEqual(second_call.args[1:3], ("Second question?", "en"))
            self.assertEqual(second_call.kwargs["model"], "gemini-3.8-flash")

            rendered = output.getvalue()
            self.assertIn("No answer yet. Ask a question first.", rendered)
            self.assertIn("[1] ifab-en:10 (printed_page=8, chunk_id=a) [cited]", rendered)
            self.assertIn(f"Saved last answer to {save_file}", rendered)

            with save_file.open(encoding="utf-8") as handle:
                saved = json.loads(handle.read().strip())
            self.assertEqual(saved["question"], "Первый вопрос?")
            self.assertEqual(saved["requested_model"], "gemini-4-argon")
            self.assertEqual(saved["note"], "Неверный вывод по автоголу")
            self.assertEqual(saved["documents"], self.documents)
            self.assertEqual(
                saved["settings"]["generation_options"]["max_output_tokens"], 32768
            )

    def test_chat_cli_continues_after_transient_error_without_reloading_index(self):
        calls = 0

        def flaky_generate(*_a, **kw):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise RuntimeError("temporary API timeout")
            return {
                "answer": "Recovered.",
                "status": "answered",
                "citations": ["ifab-en:10"],
                "model_version": kw["model"],
            }

        self.generate.side_effect = flaky_generate
        output = io.StringIO()
        inputs = iter(["Первый вопрос?", "Второй вопрос?", "/exit"])
        with (
            patch.object(sys, "argv", ["football-rules", "chat"]),
            patch("builtins.input", side_effect=lambda _prompt="": next(inputs)),
            redirect_stdout(output),
        ):
            main()

        self.embedder_loader.assert_called_once_with("qwen3-0.6b")
        self.dense.close.assert_called_once()
        rendered = output.getvalue()
        self.assertIn("Error: temporary API timeout", rendered)
        self.assertIn("Recovered.", rendered)

    def test_rerank_flag_reranks_candidates_before_packing(self):
        self.reranker_cls.return_value.rerank.return_value = self.documents
        result = ask_question(
            "Out?", "en", "gemini-2.5-flash-lite", Path("db"), rerank=True
        )
        self.reranker_cls.assert_called_once_with(model_name="qwen3-0.6b")
        self.reranker_cls.return_value.rerank.assert_called_once_with(
            "Out?", self.documents
        )
        self.assertEqual(result["settings"]["collection"], "resolved_collection")
        self.assertEqual(result["settings"]["strategy"], "hybrid+rerank")
        self.assertTrue(result["settings"]["rerank"])
