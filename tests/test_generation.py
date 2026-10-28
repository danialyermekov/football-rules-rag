import json
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from google.genai import types
from pydantic import ValidationError

from football_rules.generation import (
    EVIDENCE_CHECK_PROMPT,
    FOCUSED_PROMPT,
    GROUNDED_PROMPT,
    Answer,
    EvidenceCheckedAnswer,
    cited_documents,
    generate_answer,
    metric_value,
    valid_citations,
    valid_evidence_quotes,
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

    def test_evidence_check_is_opt_in_and_preserves_the_observable_checks(self):
        client = Mock()
        payload = {
            "checks": [
                {
                    "rule_quote": "Required rule",
                    "citation": "en:10",
                    "incident_fact": "Known fact",
                    "consequence": "Required decision",
                }
            ],
            "missing_facts": [],
            "missing_rules": [],
            "status": "answered",
            "answer": "Decision.",
            "citations": ["en:10"],
        }
        usage = Mock()
        usage.model_dump.return_value = {"prompt_token_count": 100}
        client.models.generate_content.return_value = SimpleNamespace(
            text=json.dumps(payload), model_version="test", usage_metadata=usage
        )
        result = generate_answer(
            client, "Known fact", "en", "Required rule", check_evidence=True
        )
        config = client.models.generate_content.call_args.kwargs["config"]
        self.assertIs(config.response_schema, EvidenceCheckedAnswer)
        self.assertEqual(config.system_instruction, EVIDENCE_CHECK_PROMPT)
        self.assertEqual(config.max_output_tokens, 1024)
        self.assertEqual(result["checks"], payload["checks"])
        self.assertEqual(result["citations"], ["en:10"])
        for options in [{"system_prompt": FOCUSED_PROMPT}, {"citation_documents": []}]:
            with self.subTest(options=options), self.assertRaises(ValueError):
                generate_answer(
                    client, "Known fact", "en", "rule", check_evidence=True, **options
                )

    def test_quote_provenance_rejects_invented_text_and_wrong_page(self):
        output = {
            "documents": [
                {"document_id": "en", "pdf_page": 10, "text": "Required\n rule"}
            ],
            "checks": [],
        }
        for quote, citation, expected in [
            ("Required rule", "en:10", True),
            ("Invented rule", "en:10", False),
            ("Required rule", "en:11", False),
            ("  ", "en:10", False),
        ]:
            with self.subTest(quote=quote, citation=citation):
                output["checks"] = [{"rule_quote": quote, "citation": citation}]
                self.assertEqual(valid_evidence_quotes(output), expected)

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
        for prompt in (GROUNDED_PROMPT, FOCUSED_PROMPT):
            generate_answer(client, "Question?", "en", "context", system_prompt=prompt)
            self.assertEqual(
                client.models.generate_content.call_args.kwargs[
                    "config"
                ].system_instruction,
                prompt,
            )

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

    def test_source_ids_map_to_pdf_pages_and_keep_same_page_chunks_together(self):
        client = Mock()
        usage = Mock()
        usage.model_dump.return_value = {"prompt_token_count": 100}
        client.models.generate_content.return_value = SimpleNamespace(
            text='{"status":"answered","answer":"No.","citations":["S2"]}',
            model_version="test",
            usage_metadata=usage,
        )
        documents = [
            {"document_id": "ru", "pdf_page": 151, "printed_page": 149},
            {"document_id": "ru", "pdf_page": 151, "printed_page": 149},
            {"document_id": "en", "pdf_page": 145, "printed_page": 145},
        ]
        result = generate_answer(
            client, "Question?", "en", "context", citation_documents=documents
        )
        self.assertEqual(result["citations"], ["en:145"])
        self.assertEqual(
            result["citation_source_map"], {"S1": "ru:151", "S2": "en:145"}
        )
        self.assertEqual(result["citation_source_ids"], ["S2"])
        request = client.models.generate_content.call_args.kwargs
        self.assertEqual(
            request["config"].response_schema["properties"]["citations"]["items"][
                "enum"
            ],
            ["S1", "S2"],
        )
        self.assertIn("S1 = ru:151", request["contents"])

    def test_source_ids_reject_unknown_and_duplicate_values(self):
        for citations in ['["S9"]', '["S1","S1"]']:
            client = Mock()
            client.models.generate_content.return_value = SimpleNamespace(
                text='{"status":"answered","answer":"No.","citations":'
                + citations
                + "}"
            )
            with self.subTest(citations=citations), self.assertRaises(ValueError):
                generate_answer(
                    client,
                    "Question?",
                    "en",
                    "context",
                    citation_documents=[{"document_id": "en", "pdf_page": 145}],
                )
