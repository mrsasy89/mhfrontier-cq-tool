import io
import json
import os
import unittest
import urllib.error
from unittest.mock import Mock, patch
from mhfz_builder.gemini_provider import GeminiPlanner
from test_openai_provider import Response, SETTINGS
from test_planning import intent


class Opener:
    def __init__(self, value):
        self.value = value
        self.requests = []
    def open(self, request, timeout):
        self.requests.append(request)
        return Response(json.dumps(self.value).encode())


class GeminiTests(unittest.TestCase):
    def test_key_header_schema_stateless_request_and_metadata(self):
        data = {"id": "test", "status": "completed", "model": "gemini-3.8-flash", "steps": [
            {"type": "model_output", "content": [{"type": "text", "text": json.dumps(intent())}]}],
            "usage": {"total_input_tokens": 10, "total_output_tokens": 5, "total_tokens": 15}}
        opener = Opener(data)
        client = GeminiPlanner(dict(SETTINGS, kind="gemini", model="gemini-3.8-flash"), opener)
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-secret"}):
            self.assertEqual(client.request("intent", {"type": "object"}, {}), intent())
        request = opener.requests[0]
        body = json.loads(request.data)
        self.assertNotIn("test-secret", request.full_url)
        self.assertEqual(request.get_header("X-goog-api-key"), "test-secret")
        self.assertFalse(body["store"])
        self.assertEqual(body["response_format"]["mime_type"], "application/json")
        self.assertNotIn("tools", body)
        self.assertFalse(client.calls[0]["free_tier_verified"])

    def test_missing_key_never_connects(self):
        opener = Opener({})
        with patch.dict(os.environ, {}, clear=True), self.assertRaises(ValueError):
            GeminiPlanner(SETTINGS, opener).request("intent", {}, {})
        self.assertEqual(opener.requests, [])

    def test_quota_failure_does_not_retry_or_change_provider(self):
        opener = Mock()
        opener.open.side_effect = urllib.error.HTTPError("https://example.invalid", 429, "quota", {}, io.BytesIO(b"test-secret"))
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-secret"}), self.assertRaises(ValueError) as error:
            GeminiPlanner(SETTINGS, opener).request("intent", {}, {})
        self.assertNotIn("test-secret", str(error.exception))
        self.assertEqual(opener.open.call_count, 1)

    def test_incomplete_and_tool_action_responses_are_rejected(self):
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-secret"}):
            for data in ({"status": "in_progress"}, {"status": "requires_action", "steps": [{"type": "function_call"}]}):
                with self.subTest(data=data), self.assertRaises(ValueError):
                    GeminiPlanner(SETTINGS, Opener(data)).request("intent", {}, {})
