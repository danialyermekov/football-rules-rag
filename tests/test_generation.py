import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from google.genai import types
from pydantic import ValidationError

from football_rules.generation.gemini import (
    Answer,
    cited_documents,
    generate_answer,
    metric_value,
    valid_citations,
)


class GenerationTests(unittest.TestCase):
    def test_model_thinking_and_output_limit_are_explicit_and_optional(self):
        client = Mock()
        usage = Mock()
        usage.model_dump.return_value = {"prompt_token_count": 10}
        client.models.generate_content.return_value = SimpleNamespace(
            text='{"status":"answered","answer":"No.","citations":[]}',
            model_version="test",
            usage_metadata=usage,
        )
        generate_answer(client, "Question?", "en", "rule")
        config = client.models.generate_content.call_args.kwargs["config"]
        self.assertIsNone(config.thinking_config)
        self.assertEqual(config.max_output_tokens, 1024)
        self.assertEqual(config.temperature, 0)
        generate_answer(
            client,
            "Question?",
            "en",
            "rule",
            model="gemini-3.8-flash",
            thinking_level=types.ThinkingLevel.LOW,
            max_output_tokens=2048,
        )
        request = client.models.generate_content.call_args.kwargs
        self.assertEqual(request["model"], "gemini-3.8-flash")
        self.assertEqual(
            request["config"].thinking_config.thinking_level, types.ThinkingLevel.LOW
        )
        self.assertEqual(request["config"].max_output_tokens, 2048)
        generate_answer(
            client,
            "Question?",
            "en",
            "rule",
            model="gemini-4-argon",
            thinking_level=types.ThinkingLevel.LOW,
            max_output_tokens=32768,
            temperature=None,
        )
        config = client.models.generate_content.call_args.kwargs["config"]
        self.assertNotIn("temperature", config.model_dump(exclude_none=True))
        self.assertEqual(config.max_output_tokens, 32768)
        with self.assertRaises(ValueError):
            generate_answer(client, "Question?", "en", "rule", max_output_tokens=0)

    def test_citations_resolve_only_to_supplied_pages(self):
        documents = [
            {"document_id": "en", "pdf_page": 10, "text": "first"},
            {"document_id": "en", "pdf_page": 10, "text": "second"},
            {"document_id": "ru", "pdf_page": 10, "text": "other"},
        ]
        self.assertEqual(cited_documents(["en:10"], documents), documents[:2])
        for citations, expected in [
            (["en:10"], True),
            (["en:11"], False),
            (["en:10", "en:10"], False),
            ([], False),
        ]:
            with self.subTest(citations=citations):
                self.assertEqual(
                    valid_citations({"citations": citations, "documents": documents}),
                    expected,
                )

    def test_undefined_judge_scores_are_not_successes_or_zeroes(self):
        for value in [float("nan"), float("inf"), -0.1, 1.1]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                metric_value(value)
        self.assertEqual(metric_value(0.75), 0.75)

    def test_answer_schema_rejects_unknown_status_and_empty_text(self):
        for fields in [
            {"status": "guessed", "answer": "Yes", "citations": []},
            {"status": "answered", "answer": "", "citations": []},
        ]:
            with self.subTest(fields=fields), self.assertRaises(ValidationError):
                Answer.model_validate(fields)

    def test_generation_uses_context_and_structured_output_without_reference(self):
        client = Mock()
        usage = Mock()
        usage.model_dump.return_value = {"prompt_token_count": 100}
        client.models.generate_content.return_value = SimpleNamespace(
            text='{"status":"answered","answer":"No.","citations":["en:10"]}',
            model_version="pinned-response-version",
            usage_metadata=usage,
        )
        result = generate_answer(client, "Question?", "en", "Exact selected context")
        arguments = client.models.generate_content.call_args.kwargs
        self.assertIn("Exact selected context", arguments["contents"])
        self.assertEqual(arguments["config"].temperature, 0)
        self.assertIs(arguments["config"].response_schema, Answer)
        self.assertEqual(result["citations"], ["en:10"])
        self.assertEqual(result["model_version"], "pinned-response-version")
        self.assertEqual(result["usage"]["prompt_token_count"], 100)

    def test_empty_context_returns_localized_abstention_without_api(self):
        for language, prefix in [("ru", "Недостаточно"), ("en", "There are")]:
            with self.subTest(language=language):
                client = Mock()
                result = generate_answer(client, "Question?", language, " \n\t")
                client.models.generate_content.assert_not_called()
                self.assertEqual(result["status"], "insufficient_context")
                self.assertTrue(result["answer"].startswith(prefix))
                self.assertEqual(result["citations"], [])
                self.assertFalse(result["api_called"])
                self.assertEqual(result["usage"]["prompt_token_count"], 0)

    def test_legacy_experiment_can_bypass_guard_explicitly(self):
        client = Mock()
        client.models.generate_content.return_value = SimpleNamespace(text=None)
        with self.assertRaisesRegex(ValueError, "no answer"):
            generate_answer(client, "Question?", "en", "", guard_empty_context=False)
        client.models.generate_content.assert_called_once()

    def test_empty_model_response_fails(self):
        client = Mock()
        client.models.generate_content.return_value = SimpleNamespace(text=None)
        with self.assertRaisesRegex(ValueError, "no answer"):
            generate_answer(client, "Question?", "en", "context")
