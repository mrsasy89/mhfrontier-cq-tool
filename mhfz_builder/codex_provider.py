"""Official Codex CLI integration using each user's own ChatGPT login."""
from __future__ import annotations
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import tempfile
from .prompts import INSTRUCTIONS, DOMAIN_RULES

CLI_VERSION = "0.164.0"
REQUIRED_FLAGS = ("--ignore-user-config", "--ephemeral", "--output-schema", "--output-last-message")


def child_environment():
    env = os.environ.copy()
    # Account mode must not silently select API-key authentication or a custom API URL.
    for name in ("OPENAI_API_KEY", "CODEX_API_KEY", "OPENAI_BASE_URL", "OPENAI_ORG_ID", "OPENAI_PROJECT_ID"):
        env.pop(name, None)
    return env


def native_executable(candidate):
    path = Path(candidate).expanduser().resolve()
    if not path.is_file():
        return None
    if os.name == "nt" and path.suffix.lower() == ".exe":
        return path
    if os.name != "nt" and path.name != "codex.js":
        return path
    if path.name.lower() not in ("codex.cmd", "codex.ps1", "codex", "codex.js"):
        return None
    arch = "arm64" if platform.machine().lower() in ("arm64", "aarch64") else "x64"
    system = "win32" if os.name == "nt" else "darwin" if platform.system() == "Darwin" else "linux"
    cpu = "aarch64" if arch == "arm64" else "x86_64"
    triple = f"{cpu}-pc-windows-msvc" if system == "win32" else f"{cpu}-apple-darwin" if system == "darwin" else f"{cpu}-unknown-linux-musl"
    roots = [path.parent / "node_modules/@openai/codex"]
    if path.parent.name == ".bin":
        roots.append(path.parent.parent / "@openai/codex")
    if path.name == "codex.js":
        roots.append(path.parent.parent)
    for base in roots:
        for vendor in (base / f"node_modules/@openai/codex-{system}-{arch}/vendor", base / "vendor",
                       base.parent / f"codex-{system}-{arch}/vendor"):
            exe = vendor / triple / "bin" / ("codex.exe" if os.name == "nt" else "codex")
            if exe.is_file():
                return exe.resolve()
    return None


def resolve_cli(config):
    settings = config.get("ai_provider") or {}
    explicit = settings.get("executable") if settings.get("kind") == "codex" else None
    if explicit:
        candidate = native_executable(explicit)
        if candidate:
            return candidate
        raise ValueError("Configured Codex executable is missing or unsupported; provide the official native executable")
    candidates = [shutil.which("codex"), shutil.which("codex.exe"), shutil.which("codex.cmd")]
    managed = Path(config["workspace"]) / "tools/codex"
    # Also support managed npm installations on POSIX, where .bin/codex is a Node entrypoint.
    if os.name == "nt":
        candidates.append(str(managed / "node_modules/.bin/codex.cmd"))
    else:
        candidates.append(str(managed / "node_modules/.bin/codex"))
    for value in candidates:
        if value:
            candidate = native_executable(value)
            if candidate:
                return candidate
    raise ValueError("Codex CLI is not installed: run codex-install or configure --codex-path")


def login_status(config, runner=None):
    run = runner or subprocess.run
    exe = resolve_cli(config)
    result = run([str(exe), "login", "status"], capture_output=True, text=True, encoding="utf-8",
                 errors="replace", timeout=15, env=child_environment())
    output = (result.stdout + result.stderr).lower()
    mode = "chatgpt" if result.returncode == 0 and "chatgpt" in output else "api_key" if result.returncode == 0 and "api key" in output else "unknown" if result.returncode == 0 else "signed_out"
    return {"installed": True, "executable": str(exe), "logged_in": result.returncode == 0,
            "auth_method": mode, "account_ready": mode == "chatgpt", "live_verified": False}


def login(config, device_auth=False):
    state = login_status(config)
    if state["account_ready"]:
        return state
    args = [state["executable"], "login"]
    if device_auth:
        args.append("--device-auth")
    # The official CLI owns browser/device authentication and credential storage.
    result = subprocess.run(args, env=child_environment(), timeout=300)
    if result.returncode:
        raise ValueError("Codex login did not complete; retry codex-login in your terminal")
    return login_status(config)


def install(config):
    try:
        existing = resolve_cli(config)
        return {"installed": True, "reused_existing": True, "executable": str(existing)}
    except ValueError:
        if (config.get("ai_provider") or {}).get("executable"):
            raise
    node = shutil.which("node")
    npm = shutil.which("npm")
    if not node or not npm:
        raise ValueError("Node.js and npm are required to install Codex; install the official CLI or configure its path")
    npm_path = Path(npm).resolve()
    npm_js = npm_path if npm_path.suffix == ".js" else npm_path.parent / "node_modules/npm/bin/npm-cli.js"
    if not npm_js.is_file():
        raise ValueError("Cannot locate npm-cli.js; install @openai/codex with npm, then retry")
    destination = Path(config["workspace"]) / "tools/codex"
    destination.mkdir(parents=True, exist_ok=True)
    # No shell expansion, auto-upgrade or redistribution. npm verifies package integrity.
    result = subprocess.run([node, str(npm_js), "install", "--prefix", str(destination),
                             "--no-save", "--no-audit", "--no-fund", f"@openai/codex@{CLI_VERSION}"],
                            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
    if result.returncode:
        raise ValueError("Official Codex CLI installation failed; check Node/npm and network access")
    return {"installed": True, "reused_existing": False, "executable": str(resolve_cli(config)), "version": CLI_VERSION}


class CodexPlanner:
    kind = "codex"

    def __init__(self, config, runner=None):
        self.config = config
        self.settings = config["ai_provider"]
        self.run = runner or subprocess.run
        self.calls = []
        self.checked = False

    def request(self, purpose, schema, data):
        state = login_status(self.config, self.run)
        if not state["account_ready"]:
            raise ValueError("Codex account login is required: run codex-login; API-key authentication is not used in account mode")
        executable = state["executable"]
        if not self.checked:
            help_result = self.run([executable, "exec", "--help"], capture_output=True, text=True,
                                  encoding="utf-8", errors="replace", timeout=15, env=child_environment())
            if help_result.returncode or any(flag not in help_result.stdout for flag in REQUIRED_FLAGS):
                raise ValueError("Installed Codex lacks required integration options; update the official CLI")
            self.checked = True
        home = Path(self.config["workspace"]) / "codex-runs"
        home.mkdir(parents=True, exist_ok=True)
        job = Path(tempfile.mkdtemp(prefix=f"{purpose}-", dir=home))
        schema_path, output_path = job / "schema.json", job / "result.json"
        schema_path.write_text(json.dumps(schema), encoding="utf-8")
        prompt = INSTRUCTIONS + "\n" + DOMAIN_RULES + "\nUse no tools. Return only the requested JSON.\n" + json.dumps({"task": purpose, "data": data}, ensure_ascii=False)
        if len(prompt.encode("utf-8")) > 2_000_000:
            raise ValueError("Planning context exceeds the request size limit")
        args = [executable, "exec", "--ignore-user-config", "--ephemeral", "--skip-git-repo-check",
                "--sandbox", "read-only", "--color", "never", "--json", "--cd", str(job),
                "--output-schema", str(schema_path), "--output-last-message", str(output_path)]
        for value in ('approval_policy="never"', 'project_doc_max_bytes=0', 'features.shell_tool=false',
                      'features.apps=false', 'features.remote_plugin=false', 'features.browser_use=false',
                      'features.computer_use=false', 'features.skill_search=false',
                      'features.skill_mcp_dependency_install=false', 'agents.enabled=false', 'web_search="disabled"'):
            args += ["-c", value]
        if self.settings.get("model"):
            args += ["--model", self.settings["model"]]
        args.append("-")
        with (job / "events.jsonl").open("w", encoding="utf-8") as events, (job / "stderr.log").open("w", encoding="utf-8") as errors:
            try:
                result = self.run(args, input=prompt, text=True, encoding="utf-8", errors="replace",
                                  stdout=events, stderr=errors, cwd=job,
                                  env=child_environment(), timeout=self.settings["timeout_seconds"])
            except subprocess.TimeoutExpired:
                raise ValueError(f"Codex planning timed out; no automatic retry. Local diagnostics: {job}") from None
        if result.returncode:
            raise ValueError(f"Codex planning failed; local diagnostics: {job}")
        if not output_path.is_file() or output_path.stat().st_size > 2_000_000:
            raise ValueError("Codex did not produce a bounded structured result")
        text = output_path.read_text(encoding="utf-8-sig")
        try:
            value = json.loads(text)
        except ValueError:
            raise ValueError("Codex returned invalid structured JSON") from None
        event_path = job / "events.jsonl"
        if event_path.stat().st_size > 2_000_000:
            raise ValueError("Codex event stream exceeds the size limit")
        usage = {}
        thread_id = None
        for line in event_path.read_text(encoding="utf-8").splitlines():
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if event.get("type") in ("turn.failed", "error"):
                raise ValueError("Codex reported a failed turn; no plan accepted")
            if event.get("type") == "thread.started":
                thread_id = event.get("thread_id")
            if event.get("type") == "turn.completed":
                usage = event.get("usage", {})
            if event.get("item", {}).get("type") in ("command_execution", "file_change", "mcp_tool_call", "web_search"):
                raise ValueError("Codex attempted a tool action during a planning-only request")
        self.calls.append({"provider": "codex", "purpose": purpose, "auth_method": "chatgpt",
                           "thread_id": thread_id, "usage": usage, "diagnostics": str(job),
                           "model": self.settings.get("model") or "Codex account default"})
        return value
