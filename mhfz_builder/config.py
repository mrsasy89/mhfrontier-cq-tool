from __future__ import annotations
import json
from pathlib import Path

CONFIG_NAME = "quest-builder.local.json"


def contains(parent: Path, child: Path) -> bool:
    return child.resolve().is_relative_to(parent.resolve())


def validate(config: dict) -> dict:
    source = Path(config["source"]).resolve()
    workspace = Path(config["workspace"]).resolve()
    if not source.is_dir():
        raise ValueError(f"Corpus directory not found: {source}")
    if contains(source, workspace) or contains(workspace, source):
        raise ValueError("Corpus and workspace must be separate, non-nested directories")
    if config.get("source_kind") not in ("server", "project"):
        raise ValueError("source_kind must be server or project")
    config = dict(config, source=str(source), workspace=str(workspace))
    if config.get("refrontier"):
        config["refrontier"] = str(Path(config["refrontier"]).resolve())
    return config


def load(path: Path) -> dict:
    if not path.is_file():
        raise ValueError(f"Configuration missing: use init ({path})")
    return validate(json.loads(path.read_text(encoding="utf-8-sig")))


def initialize(path: Path, source: Path, refrontier: str | None,
               source_kind: str = "project", workspace: Path | None = None) -> dict:
    if path.exists():
        raise ValueError("Configuration already exists: preserve it or choose a different --config")
    config = validate({"schema_version": 1, "source_kind": source_kind,
                       "source": str(source.resolve()),
                       "workspace": str((workspace or path.parent / ".workspace").resolve()),
                       "refrontier": refrontier, "refrontier_mode": "legacy",
                       "ai_provider": {"kind": "codex", "model": None, "executable": None, "timeout_seconds": 180}, "gui_optional": True})
    if contains(Path(config["source"]), path):
        raise ValueError("Configuration cannot be written inside the corpus")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(config, stream, ensure_ascii=False, indent=2)
    return config


def configure_ai(path: Path, model: str | None, max_output_tokens: int = 4096,
                 provider: str = "codex", executable: str | None = None) -> dict:
    import hashlib
    import re
    import tempfile
    from .providers import settings
    config = load(path)
    if contains(Path(config["source"]), path):
        raise ValueError("Configuration cannot be written inside the corpus")
    if model is not None and not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,99}", model):
        raise ValueError("Invalid API model identifier")
    if provider == "codex":
        config["ai_provider"] = {"kind": "codex", "model": model, "executable": str(Path(executable).expanduser().resolve()) if executable else None, "timeout_seconds": 180}
    else:
        from .gemini_provider import DEFAULT_MODEL as gemini_model
        from .openai_provider import DEFAULT_MODEL as openai_model
        config["ai_provider"] = {"kind": provider, "model": model or (gemini_model if provider == "gemini" else openai_model),
                                 "max_output_tokens": max_output_tokens, "timeout_seconds": 90}
    settings(config)
    backup = replace_config(path, config)
    return {"provider": provider, "model": config["ai_provider"]["model"], "config_backup": str(backup),
            "authentication": "Personal Codex/ChatGPT account" if provider == "codex" else "Local API key; never stored by this application",
            "notice": "Gemini free-tier eligibility and quotas depend on your Google project." if provider == "gemini" else None}


def replace_config(path: Path, config: dict) -> Path:
    import hashlib
    import tempfile
    config = validate(config)
    if contains(Path(config["source"]), path):
        raise ValueError("Configuration cannot be written inside the corpus")
    original = path.read_bytes()
    sha = hashlib.sha256(original).hexdigest()
    backup = Path(config["workspace"]) / "config-backups" / f"{sha}.json"
    backup.parent.mkdir(parents=True, exist_ok=True)
    if backup.exists():
        if backup.read_bytes() != original:
            raise ValueError("Configuration backup hash mismatch")
    else:
        with backup.open("xb") as stream:
            stream.write(original)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=".quest-builder-", suffix=".local.json", delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(config, stream, ensure_ascii=False, indent=2)
        temporary.replace(path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
    return backup
