import io
from contextlib import redirect_stdout, redirect_stderr
import json
import os
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch
from test_core import fixture
from test_planning import intent, plan
from mhfz_builder.config import initialize, load, configure_ai
from mhfz_builder.corpus import scan
from mhfz_builder.planning import INTENT_SCHEMA
from mhfz_builder.openai_provider import OpenAIPlanner, NoRedirect, create_plan, status


SETTINGS = {"kind": "openai", "model": "test-model", "max_output_tokens": 4096, "timeout_seconds": 90}


def response(value, status="completed", content=None):
    return {"id": "resp_test", "status": status, "model": "test-model",
            "usage": {"input_tokens": 20, "output_tokens": 10, "total_tokens": 30},
            "output": [{"type": "message", "content": content or [{"type": "output_text", "text": json.dumps(value)}]}]}


class Response(io.BytesIO):
    headers = {"x-request-id": "req_test"}


class Opener:
    def __init__(self, result):
        self.result = result
        self.requests = []

    def open(self, request, timeout):
        self.requests.append(request)
        return Response(json.dumps(self.result).encode())


class TransportTests(unittest.TestCase):
    def test_missing_key_never_opens_connection(self):
        opener = Opener(response(intent()))
        with patch.dict(os.environ, {}, clear=True), self.assertRaises(ValueError):
            OpenAIPlanner(SETTINGS, opener).request("intent", INTENT_SCHEMA, {})
        self.assertEqual(opener.requests, [])

    def test_responses_schema_store_and_key_are_sent_correctly(self):
        opener = Opener(response(intent()))
        client = OpenAIPlanner(SETTINGS, opener)
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-secret"}):
            self.assertEqual(client.request("intent", INTENT_SCHEMA, {"prompt": "Toa"}), intent())
        req = opener.requests[0]
        body = json.loads(req.data)
        self.assertEqual(req.full_url, "https://api.openai.com/v1/responses")
        self.assertEqual(req.get_header("Authorization"), "Bearer test-secret")
        self.assertFalse(body["store"])
        self.assertTrue(body["text"]["format"]["strict"])
        self.assertNotIn("test-secret", str(body))
        self.assertNotIn("test-secret", str(client.calls))
        self.assertEqual(client.calls[0]["usage"]["total_tokens"], 30)

    def test_incomplete_refused_and_malformed_output_are_rejected(self):
        examples = [response(intent(), status="incomplete"),
                    response(None, content=[{"type": "refusal", "refusal": "no"}]),
                    response(None, content=[{"type": "output_text", "text": "not JSON"}]),
                    response(None, content=[{"type": "output_text", "text": "{}"}, {"type": "output_text", "text": "{}"}])]
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-secret"}):
            for example in examples:
                with self.subTest(example=example), self.assertRaises(ValueError):
                    OpenAIPlanner(SETTINGS, Opener(example)).request("intent", INTENT_SCHEMA, {})

    def test_http_error_body_is_not_exposed_and_not_retried(self):
        opener = unittest.mock.Mock()
        opener.open.side_effect = urllib.error.HTTPError("https://api.openai.com/v1/responses", 401, "unauthorized", {}, io.BytesIO(b"test-secret"))
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-secret"}), self.assertRaises(ValueError) as error:
            OpenAIPlanner(SETTINGS, opener).request("intent", INTENT_SCHEMA, {})
        self.assertNotIn("test-secret", str(error.exception))
        self.assertEqual(opener.open.call_count, 1)

    def test_redirect_does_not_forward_credentials(self):
        with self.assertRaises(ValueError):
            NoRedirect().redirect_request(None, None, 307, "redirect", {}, "https://other.invalid")


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        self.source = root / "quests"
        self.source.mkdir()
        self.path = root / "config.local.json"
        initialize(self.path, self.source, None)
        configure_ai(self.path, "test-model", provider="openai")
        self.config = load(self.path)

    def test_configuration_preserves_previous_bytes_and_contains_no_key(self):
        previous = self.path.read_bytes()
        result = configure_ai(self.path, "second-model", provider="openai")
        self.assertEqual(Path(result["config_backup"]).read_bytes(), previous)
        self.assertNotIn("api_key", self.path.read_text().lower())
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(status(load(self.path))["api_key_present"])
        self.assertFalse(status(self.config)["live_verified"])

    def test_model_and_token_limits_are_checked_before_configuration_changes(self):
        previous = self.path.read_bytes()
        for model, limit in (("bad model", 4096), ("test", 1)):
            with self.assertRaises(ValueError):
                configure_ai(self.path, model, limit, provider="openai")
        self.assertEqual(self.path.read_bytes(), previous)

    def test_two_stage_plan_uses_local_references_and_never_sends_paths(self):
        (self.source / "quest.bin").write_bytes(fixture())
        scan(self.config)
        opener = Opener(response(intent()))
        results = iter([response(intent()), response(plan())])
        def open_request(req, timeout):
            opener.requests.append(req)
            return Response(json.dumps(next(results)).encode())
        opener.open = open_request
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-secret"}):
            value = create_plan(self.config, "Toa in the Tower", OpenAIPlanner(SETTINGS, opener))
        self.assertEqual(len(opener.requests), 2)
        self.assertEqual(value["status"], "needs_review")
        self.assertFalse(value["bin_generated"])
        transmitted = json.loads(json.loads(opener.requests[1].data)["input"])["data"]["references"]
        self.assertNotIn("source_variants", transmitted[0])
        self.assertNotIn("texts", transmitted[0]["quest"])
        self.assertTrue(Path(value["references"][0]["source_variants"][0]).parent.samefile(self.source))
        self.assertEqual((self.source / "quest.bin").read_bytes(), fixture())


class CommandTests(unittest.TestCase):
    setUp = IntegrationTests.setUp
    def test_existing_output_stops_before_api_calls(self):
        from mhfz_builder.cli import main
        output = self.source.parent / "existing.json"
        output.write_text("preserved")
        with patch("mhfz_builder.providers.create_plan") as call, redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            code = main(["--config", str(self.path), "plan", "--prompt", "Toa", "--output", str(output)])
        self.assertEqual(code, 2)
        call.assert_not_called()
        self.assertEqual(output.read_text(), "preserved")

    def test_masked_key_is_removed_after_a_failed_request(self):
        from mhfz_builder.cli import main
        output = self.source.parent / "failed.json"
        with patch.dict(os.environ, {}, clear=True), patch("getpass.getpass", return_value="test-secret"), patch("mhfz_builder.providers.create_plan", side_effect=ValueError("simulated failure")), redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            code = main(["--config", str(self.path), "plan", "--prompt", "Toa", "--ask-key", "--output", str(output)])
            self.assertNotIn("OPENAI_API_KEY", os.environ)
        self.assertEqual(code, 2)
        self.assertFalse(output.exists())

    def test_dry_run_saves_preflight_without_api_or_key_prompt(self):
        from mhfz_builder.cli import main
        (self.source / "quest.bin").write_bytes(fixture())
        scan(self.config)
        output = self.source.parent / "preflight.json"
        with patch("mhfz_builder.providers.create_plan") as call, patch("getpass.getpass") as ask, redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            code = main(["--config", str(self.path), "plan", "--prompt", "Toa", "--ask-key", "--dry-run", "--output", str(output)])
        self.assertEqual(code, 0)
        call.assert_not_called()
        ask.assert_not_called()
        self.assertEqual(json.loads(output.read_text())["api_calls"], [])
