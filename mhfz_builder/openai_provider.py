"""OpenAI Responses transport and bounded quest planning. No shell or BIN writes."""
from __future__ import annotations
import json
import os
import urllib.error
import urllib.request

from .prompts import DOMAIN_RULES, INSTRUCTIONS

ENDPOINT = "https://api.openai.com/v1/responses"
DEFAULT_MODEL = "gpt-6.1-sol"


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Unexpected API redirect; no credentials forwarded")


class OpenAIPlanner:
    kind = "openai"
    def __init__(self, settings, opener=None):
        self.settings = settings
        self.opener = opener or urllib.request.build_opener(NoRedirect())
        self.calls = []

    def request(self, purpose, schema, data):
        key = os.environ.get("OPENAI_API_KEY", "").strip()
        if not key:
            raise ValueError("OPENAI_API_KEY is missing; configure it locally before using plan")
        payload = {"model": self.settings["model"], "store": False,
                   "max_output_tokens": self.settings["max_output_tokens"],
                   "instructions": INSTRUCTIONS + "\n" + DOMAIN_RULES,
                   "input": json.dumps({"task": purpose, "data": data}, ensure_ascii=False),
                   "text": {"format": {"type": "json_schema", "name": purpose,
                                         "strict": True, "schema": schema}}}
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        if len(body) > 2_000_000:
            raise ValueError("Planning context exceeds the request size limit")
        request = urllib.request.Request(ENDPOINT, data=body, method="POST",
                  headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
        try:
            with self.opener.open(request, timeout=self.settings["timeout_seconds"]) as response:
                raw = response.read(2_000_001)
                request_id = response.headers.get("x-request-id")
        except urllib.error.HTTPError as exc:
            messages = {401: "API authentication failed; check OPENAI_API_KEY",
                        403: "API access denied; check project/model permissions",
                        404: "API model or endpoint unavailable; check the configured model",
                        429: "API rate or quota limit reached; no automatic retry was made"}
            message = messages.get(exc.code, f"API request failed with HTTP {exc.code}; no automatic retry was made")
            exc.close()
            raise ValueError(message) from None
        except (urllib.error.URLError, TimeoutError) as exc:
            raise ValueError("API connection failed or timed out; no automatic retry was made") from None
        if len(raw) > 2_000_000:
            raise ValueError("API response exceeds the size limit")
        try:
            result = json.loads(raw)
        except (ValueError, UnicodeError):
            raise ValueError("API returned invalid JSON") from None
        if not isinstance(result, dict) or result.get("status") != "completed":
            raise ValueError("API response was incomplete or failed; no plan accepted")
        texts = []
        try:
            for item in result.get("output", []):
                if item.get("type") != "message":
                    continue
                for part in item.get("content", []):
                    if part.get("type") == "refusal":
                        raise ValueError("The model refused the planning request")
                    if part.get("type") == "output_text":
                        texts.append(part["text"])
            if len(texts) != 1 or not isinstance(texts[0], str):
                raise ValueError("API did not return one structured result")
            value = json.loads(texts[0])
        except (KeyError, TypeError, AttributeError, json.JSONDecodeError):
            raise ValueError("API returned an invalid structured result") from None
        usage = result.get("usage") or {}
        if not isinstance(usage, dict):
            raise ValueError("API returned invalid usage metadata")
        self.calls.append({"purpose": purpose, "response_id": result.get("id"),
                           "request_id": request_id, "model": result.get("model", self.settings["model"]),
                           "usage": {k: usage[k] for k in ("input_tokens", "output_tokens", "total_tokens") if k in usage}})
        return value


def settings(config):
    value = config.get("ai_provider")
    if not isinstance(value, dict) or value.get("kind") != "openai":
        raise ValueError("OpenAI is not configured: run ai-configure first")
    if not isinstance(value.get("model"), str) or not value["model"].strip():
        raise ValueError("The API model must be configured")
    if type(value.get("max_output_tokens")) is not int or not 256 <= value["max_output_tokens"] <= 16384:
        raise ValueError("max_output_tokens must be between 256 and 16384")
    if type(value.get("timeout_seconds")) is not int or not 1 <= value["timeout_seconds"] <= 300:
        raise ValueError("timeout_seconds must be between 1 and 300")
    return value


def status(config):
    configured = isinstance(config.get("ai_provider"), dict)
    if configured:
        settings(config)
    return {"configured": configured, "provider": "openai" if configured else None,
            "model": config["ai_provider"]["model"] if configured else None,
            "api_key_present": bool(os.environ.get("OPENAI_API_KEY", "").strip()),
            "live_verified": False}


def create_plan(config, prompt, planner=None):
    """Compatibility entry point for callers selecting the OpenAI API explicitly."""
    from .pipeline import create_plan as run_pipeline
    return run_pipeline(config, prompt, planner or OpenAIPlanner(settings(config)))
