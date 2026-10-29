"""Explicit provider routing. Codex account mode is primary; no automatic fallback."""
import os
from . import codex_provider
from .openai_provider import OpenAIPlanner, settings as openai_settings
from .gemini_provider import GeminiPlanner, DEFAULT_MODEL as GEMINI_MODEL


def settings(config):
    value = config.get("ai_provider") or {"kind": "codex", "model": None, "executable": None, "timeout_seconds": 180}
    if not isinstance(value, dict):
        raise ValueError("Invalid AI provider settings")
    kind = value.get("kind")
    if kind == "openai":
        return openai_settings(dict(config, ai_provider=value))
    if kind not in ("codex", "gemini"):
        raise ValueError("Unknown AI provider: choose codex, gemini or openai")
    if type(value.get("timeout_seconds")) is not int or not 1 <= value["timeout_seconds"] <= 600:
        raise ValueError("Provider timeout_seconds must be between 1 and 600")
    model = value.get("model")
    if model is not None and (not isinstance(model, str) or not model.strip()):
        raise ValueError("Invalid provider model")
    if kind == "gemini":
        if not model:
            raise ValueError("Gemini model must be configured")
        if type(value.get("max_output_tokens")) is not int or not 256 <= value["max_output_tokens"] <= 16384:
            raise ValueError("max_output_tokens must be between 256 and 16384")
    elif value.get("executable") is not None and not isinstance(value["executable"], str):
        raise ValueError("Codex executable must be a path")
    return value


def status(config):
    value = settings(config)
    result = {"configured": True, "provider": value["kind"], "model": value.get("model"), "live_verified": False}
    if value["kind"] == "codex":
        try:
            result.update(codex_provider.login_status(dict(config, ai_provider=value)))
        except (ValueError, OSError, TimeoutError) as exc:
            result.update(installed=False, account_ready=False, detail=str(exc))
    else:
        env = key_environment(value["kind"])
        result["api_key_present"] = bool(os.environ.get(env, "").strip())
        if value["kind"] == "gemini":
            result.update(free_tier_verified=False, billing_notice="Use your own free-tier project; eligibility, quotas and billing are controlled by Google.")
    return result


def key_environment(kind):
    if kind == "codex":
        return None
    return "GEMINI_API_KEY" if kind == "gemini" else "OPENAI_API_KEY"


def create_client(config):
    value = settings(config)
    if value["kind"] == "codex":
        return codex_provider.CodexPlanner(dict(config, ai_provider=value))
    if value["kind"] == "gemini":
        return GeminiPlanner(value)
    return OpenAIPlanner(value)


def create_plan(config, prompt):
    from .pipeline import create_plan as run_pipeline
    return run_pipeline(config, prompt, create_client(config))


def local_api_key(config, ask=False, reader=None):
    """Scoped, masked API key prompt shared by planning and typed compilation."""
    from contextlib import contextmanager
    import getpass
    @contextmanager
    def scope():
        kind = settings(config)["kind"]
        if ask and kind == "codex":
            raise ValueError("Codex account mode uses codex-login; no API key is required")
        name = key_environment(kind)
        temporary = ask and not os.environ.get(name, "").strip()
        if temporary:
            os.environ[name] = (reader or getpass.getpass)(f"{kind} API key (not saved): ")
        try:
            yield
        finally:
            if temporary:
                os.environ.pop(name, None)
    return scope()
