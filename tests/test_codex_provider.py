import json
import os
import platform
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from mhfz_builder.codex_provider import CodexPlanner, REQUIRED_FLAGS, login_status, native_executable, install
from mhfz_builder.providers import settings
from test_planning import intent


class CodexTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.exe = self.root / "codex.exe"
        self.exe.write_bytes(b"test fixture only")
        self.config = {"workspace": str(self.root / "work"), "ai_provider": {
            "kind": "codex", "model": None, "executable": str(self.exe), "timeout_seconds": 180}}
        self.commands = []
        self.auth = "Logged in using ChatGPT"
        self.output = json.dumps(intent())
        self.tool_action = False

    def runner(self, args, **kwargs):
        self.commands.append((args, kwargs))
        if args[1:] == ["login", "status"]:
            return subprocess.CompletedProcess(args, 0, "", self.auth)
        if args[1:] == ["exec", "--help"]:
            return subprocess.CompletedProcess(args, 0, " ".join(REQUIRED_FLAGS), "")
        output = Path(args[args.index("--output-last-message") + 1])
        output.write_text(self.output, encoding="utf-8")
        events = [{"type": "thread.started", "thread_id": "test-thread"},
                  {"type": "turn.completed", "usage": {"input_tokens": 20, "output_tokens": 10}}]
        if self.tool_action:
            events.insert(1, {"type": "item.started", "item": {"type": "command_execution"}})
        for event in events:
            kwargs["stdout"].write(json.dumps(event) + "\n")
        return subprocess.CompletedProcess(args, 0)

    def test_personal_login_stdin_schema_and_restricted_execution(self):
        client = CodexPlanner(self.config, self.runner)
        with patch.dict(os.environ, {"OPENAI_API_KEY": "must-not-pass", "CODEX_API_KEY": "must-not-pass"}):
            self.assertEqual(client.request("intent", {"type": "object"}, {"prompt": "a ; $(shell) & b"}), intent())
        args, kwargs = self.commands[-1]
        self.assertIn("--ignore-user-config", args)
        self.assertIn("--ephemeral", args)
        self.assertEqual(args[args.index("--sandbox") + 1], "read-only")
        self.assertIn("features.shell_tool=false", args)
        self.assertNotIn("--dangerously-bypass-approvals-and-sandbox", args)
        self.assertNotIn("OPENAI_API_KEY", kwargs["env"])
        self.assertNotIn("CODEX_API_KEY", kwargs["env"])
        self.assertNotIn("a ; $(shell) & b", args)
        self.assertIn("a ; $(shell) & b", kwargs["input"])
        self.assertEqual(client.calls[0]["auth_method"], "chatgpt")

    def test_api_key_login_never_launches_inference(self):
        self.auth = "Logged in using an API key"
        with self.assertRaises(ValueError):
            CodexPlanner(self.config, self.runner).request("intent", {}, {})
        self.assertEqual(len(self.commands), 1)

    def test_bad_json_and_unexpected_tool_events_are_rejected(self):
        self.output = "not JSON"
        with self.assertRaises(ValueError):
            CodexPlanner(self.config, self.runner).request("intent", {}, {})
        self.output = json.dumps(intent())
        self.tool_action = True
        with self.assertRaises(ValueError):
            CodexPlanner(self.config, self.runner).request("intent", {}, {})

    def test_installed_cli_is_reused_without_downloading(self):
        with patch("mhfz_builder.codex_provider.resolve_cli", return_value=self.exe), patch("mhfz_builder.codex_provider.subprocess.run") as run:
            value = install(self.config)
        self.assertTrue(value["reused_existing"])
        run.assert_not_called()

    def test_native_resolution_handles_local_npm_layout(self):
        base = self.root / "npm/node_modules/@openai/codex"
        arch = "arm64" if platform.machine().lower() in ("arm64", "aarch64") else "x64"
        cpu = "aarch64" if arch == "arm64" else "x86_64"
        system = "win32" if os.name == "nt" else "darwin" if platform.system() == "Darwin" else "linux"
        triple = f"{cpu}-pc-windows-msvc" if os.name == "nt" else f"{cpu}-apple-darwin" if system == "darwin" else f"{cpu}-unknown-linux-musl"
        exe = base.parent / f"codex-{system}-{arch}/vendor" / triple / "bin" / ("codex.exe" if os.name == "nt" else "codex")
        exe.parent.mkdir(parents=True)
        exe.write_bytes(b"fixture")
        shim = self.root / "npm/node_modules/.bin/codex.cmd" if os.name == "nt" else base / "bin/codex.js"
        shim.parent.mkdir(parents=True, exist_ok=True)
        shim.write_text("fixture")
        self.assertTrue(native_executable(shim).samefile(exe))

    def test_unconfigured_provider_defaults_to_codex(self):
        self.assertEqual(settings({"ai_provider": None})["kind"], "codex")


class ProviderRoutingTests(unittest.TestCase):
    def test_configuration_defaults_to_codex_and_provider_failure_does_not_fall_back(self):
        from mhfz_builder.config import initialize, configure_ai, load
        from mhfz_builder.providers import create_plan
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            corpus = root / "quests"; corpus.mkdir()
            config_file = root / "config.local.json"
            config = initialize(config_file, corpus, None)
            self.assertEqual(config["ai_provider"]["kind"], "codex")
            configure_ai(config_file, None)
            config = load(config_file)
            self.assertEqual(config["ai_provider"]["kind"], "codex")
            with patch("mhfz_builder.providers.codex_provider.CodexPlanner", side_effect=ValueError("account limit")), patch("mhfz_builder.providers.OpenAIPlanner") as api, patch("mhfz_builder.providers.GeminiPlanner") as gemini:
                with self.assertRaises(ValueError):
                    create_plan(config, "Toa")
            api.assert_not_called()
            gemini.assert_not_called()
