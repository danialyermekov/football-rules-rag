import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

import mlflow

from football_rules.query_rewriting import REWRITE_PROMPT, rewrite_query


class QueryRewriteTests(unittest.TestCase):
    def setUp(self):
        original = mlflow.get_tracking_uri()
        mlflow.set_tracking_uri("sqlite:///:memory:")
        self.addCleanup(mlflow.set_tracking_uri, original)
        mlflow.tracing.disable()
        self.addCleanup(mlflow.tracing.enable)
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.cache = Path(directory.name)
        self.client = Mock()
        self.response = self.client.models.generate_content.return_value
        self.response.text = '{"rewritten_query":"defective ball restart"}'
        self.response.model_version = "fixture"
        self.response.usage_metadata.model_dump.return_value = {
            "prompt_token_count": 10,
            "candidates_token_count": 5,
        }
        self.response.model_dump.return_value = {"text": self.response.text}

    def test_only_question_and_language_sent_and_valid_response_cached(self):
        first = rewrite_query(
            self.client, "The ball burst. What now?", "en", self.cache
        )
        request = self.client.models.generate_content.call_args.kwargs
        self.assertEqual(
            request["contents"], "LANGUAGE: en\nQUESTION:\nThe ball burst. What now?"
        )
        self.assertEqual(request["config"].system_instruction, REWRITE_PROMPT)
        self.assertTrue(first["api_called"])
        second = rewrite_query(
            self.client, "The ball burst. What now?", "en", self.cache
        )
        self.client.models.generate_content.assert_called_once()
        self.assertFalse(second["api_called"])
        self.assertEqual(first["rewritten_query"], second["rewritten_query"])
        cache = next(self.cache.glob("*.json"))
        saved = json.loads(cache.read_text())
        saved["request"]["query"] = "tampered"
        cache.write_text(json.dumps(saved))
        with self.assertRaises(ValueError):
            rewrite_query(self.client, "The ball burst. What now?", "en", self.cache)

    def test_invalid_inputs_and_invalid_model_output_rejected(self):
        for query, lang in [(" ", "en"), ("ball", "de")]:
            with self.assertRaises(ValueError):
                rewrite_query(self.client, query, lang, self.cache)
        self.client.models.generate_content.assert_not_called()
        for text in [None, "{}", '{"rewritten_query":" "}']:
            self.response.text = text
            with self.assertRaises(ValueError):
                rewrite_query(self.client, "ball", "en", self.cache)
        self.assertFalse(list(self.cache.glob("*.json")))
