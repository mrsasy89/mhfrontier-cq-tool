"""Optional Gemini free-tier-capable adapter; the account controls billing and quotas."""
import json
import os
import urllib.request
import urllib.error
from .openai_provider import NoRedirect
from .prompts import INSTRUCTIONS, DOMAIN_RULES

ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/interactions"
DEFAULT_MODEL = "gemini-3.8-flash"


class GeminiPlanner:
    kind = "gemini"

    def __init__(self, settings, opener=None):
        self.settings = settings
        self.opener = opener or urllib.request.build_opener(NoRedirect())
        self.calls = []

    def request(self, purpose, schema, data):
        key = os.environ.get("GEMINI_API_KEY", "").strip()
        if not key:
            raise ValueError("GEMINI_API_KEY is missing; use --ask-key or configure it locally")
        payload = {"model": self.settings["model"], "store": False,
                   "system_instruction": INSTRUCTIONS + "\n" + DOMAIN_RULES,
                   "input": json.dumps({"task": purpose, "data": data}, ensure_ascii=False),
                   "generation_config": {"max_output_tokens": self.settings["max_output_tokens"]},
                   "response_format": {"type": "text", "mime_type": "application/json", "schema": schema}}
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        if len(body) > 2_000_000:
            raise ValueError("Planning context exceeds the request size limit")
        request = urllib.request.Request(ENDPOINT, data=body, method="POST",
                                         headers={"x-goog-api-key": key, "Content-Type": "application/json"})
        try:
            with self.opener.open(request, timeout=self.settings["timeout_seconds"]) as response:
                raw = response.read(2_000_001)
        except urllib.error.HTTPError as exc:
            code = exc.code
            exc.close()
            if code == 429:
                raise ValueError("Gemini quota/rate limit reached; no retry or provider/billing switch was made") from None
            raise ValueError(f"Gemini request failed with HTTP {code}; check your key, model and project access") from None
        except (urllib.error.URLError, TimeoutError):
            raise ValueError("Gemini connection failed or timed out; no automatic retry") from None
        if len(raw) > 2_000_000:
            raise ValueError("Gemini response exceeds the size limit")
        try:
            result = json.loads(raw)
            if not isinstance(result, dict) or result.get("status") != "completed":
                raise ValueError("Gemini response was incomplete, blocked or failed")
            texts = [part["text"] for step in result.get("steps", []) if step.get("type") == "model_output"
                     for part in step.get("content", []) if part.get("type") == "text"]
            if len(texts) != 1:
                raise ValueError("Gemini did not return one structured result")
            value = json.loads(texts[0])
            usage = result.get("usage") or {}
            if not isinstance(usage, dict):
                raise ValueError("Invalid Gemini usage metadata")
        except (KeyError, TypeError, AttributeError, UnicodeError, json.JSONDecodeError):
            raise ValueError("Gemini returned an invalid structured result") from None
        self.calls.append({"provider": "gemini", "purpose": purpose, "response_id": result.get("id"),
                           "model": result.get("model", self.settings["model"]),
                           "usage": {k: usage[k] for k in ("total_input_tokens", "total_output_tokens", "total_tokens") if k in usage},
                           "free_tier_verified": False})
        return value
