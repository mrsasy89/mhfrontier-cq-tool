import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from test_core import fixture
from mhfz_builder.authoring import collect_preferences, parse_flags, enforce_preferences
from mhfz_builder.config import initialize
from mhfz_builder.corpus import scan
from mhfz_builder.gui_session import GuiConsole
from mhfz_builder.gui_session import run as run_gui
from mhfz_builder.reward_editor import save_draft
from mhfz_builder.gui_safety import prepare_save
from mhfz_builder.wizard import Console, create_quest


class AuthoringTests(unittest.TestCase):
    def ui(self, answers):
        values = iter(answers)
        return Console(lambda _: next(values), lambda _: None)

    def test_fixed_question_order_and_back_preserve_explicit_choices(self):
        choices = collect_preferences(self.ui(["34", "b", "35", "", "+1:2 -3:32", ""]))
        self.assertEqual(choices, {"stat_table": 35, "position": "native", "position_request": "", "flags": {"1:2": True, "3:32": False}, "rewards": "native"})

    def test_unknown_reserved_combined_and_duplicate_flags_are_rejected(self):
        for text in ("+1:16", "+3:64", "+4:1", "+1:3", "+1:2 -1:2", "yes"):
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse_flags(text)

    def test_native_preferences_override_model_changes(self):
        spec = {"edits": {"stat_table": 99, "quest_flags": [255]*4}}
        enforce_preferences({}, spec, {"stat_table": None, "flags": {}})
        self.assertIsNone(spec["edits"]["stat_table"])
        self.assertIsNone(spec["edits"]["quest_flags"])

    def test_manual_position_reaches_the_shared_planner_and_preserves_request(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); source = root / "corpus"; source.mkdir()
            (source / "65026d0.bin").write_bytes(fixture())
            config = initialize(root / "config.json", source, None); scan(config)
            answers = ["", "Create a quest", "END", "", "2", "Area 5", "", "", "yes"]
            project={'status':'needs_reference','plan':{'summary':'No compatible base','questions':[]},'references':[]}
            with patch("mhfz_builder.wizard.create_plan", return_value=project) as model, patch('mhfz_builder.wizard.ensure_provider',return_value=True):
                create_quest(config, self.ui(answers))
            model.assert_called_once()
            self.assertIn('Requested spawn position: Area 5',model.call_args.args[1])
            request = next((Path(config["workspace"]) / "sessions").glob("*/authoring-request.json"))
            self.assertEqual(json.loads(request.read_text())["choices"]["position_request"], "Area 5")
            self.assertFalse((Path(config["workspace"]) / "custom-quests").exists())

    def test_reward_draft_validates_and_preserves_anomalous_weights(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "draft.json"
            rows = [{"slot": "Main", "item_id": 10, "name": "Test item", "quantity": 2, "rate": 90}]
            value = save_draft(target, rows)
            self.assertFalse(value["bin_encoded"])
            self.assertEqual(value["totals"], {"Main": 90})
            self.assertTrue(value["warnings"])
            with self.assertRaises(FileExistsError): save_draft(target, rows)
            with self.assertRaises(ValueError): save_draft(Path(tmp) / "bad.json", [{**rows[0], "rate": 101}])

    def test_graphical_multiline_is_one_answer_without_end_marker(self):
        stdout = io.StringIO()
        with patch("sys.stdin", io.StringIO(json.dumps({"answer": "HR quest\n50 minutes\nNative rewards"}) + "\n")), patch("sys.stdout", stdout):
            text = GuiConsole().description()
        self.assertEqual(text, "HR quest\n50 minutes\nNative rewards")
        self.assertTrue(json.loads(stdout.getvalue())["multiline"])

    def test_native_editor_save_guard_preserves_original_and_rejects_server(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); source = root / "corpus"; source.mkdir()
            config = initialize(root / "config.json", source, None)
            server = root / "server"; server.mkdir()
            config["server_quest_directory"] = str(server)
            output = Path(config["workspace"]) / "custom-quests" / "test.bin"
            output.parent.mkdir(parents=True); output.write_bytes(b"original")
            value = prepare_save(config, output)
            self.assertEqual(Path(value["backup"]).read_bytes(), b"original")
            self.assertEqual(output.read_bytes(), b"original")
            self.assertEqual(prepare_save(config, output)["backup"], value["backup"])
            for forbidden in (source / "quest.bin", server / "quest.bin", root / "outside.bin"):
                with self.assertRaisesRegex(ValueError, "workspace"):
                    prepare_save(config, forbidden)
            # A server directory nested inside the workspace is protected too.
            config["server_quest_directory"] = str(output.parent)
            with self.assertRaises(ValueError): prepare_save(config, output)

    def test_gui_starts_with_provider_then_map_preview_without_terminal_menu(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); source = root / "corpus"; source.mkdir()
            (source / "65026d0.bin").write_bytes(fixture())
            path = root / "config.json"; config = initialize(path, source, None); scan(config)
            answers = [{"kind": "codex", "model": ""}, "44", "b", "b"]
            incoming = "".join(json.dumps({"answer": json.dumps(value) if isinstance(value, dict) else value}) + "\n" for value in answers)
            maps = [{"id": "44", "name": "Top of Great Forest", "references": 1,
                     "overviews": [{"path": root / "overview.png", "label": "Whole map", "display_crop": [0, 0, 256, 240]}]}]
            output = io.StringIO()
            with patch("sys.stdin", io.StringIO(incoming)), patch("sys.stdout", output), patch("mhfz_builder.gui_session.ensure_provider", return_value=True) as account, patch("mhfz_builder.map_browser.rows", return_value=maps), patch("mhfz_builder.wizard.create_plan") as model:
                self.assertEqual(run_gui(path), 0)
            events = [json.loads(line) for line in output.getvalue().splitlines()]
            questions = [event for event in events if event["kind"] == "question"]
            self.assertEqual([event["control"] for event in questions], ["provider", "map", "description", "map", "provider"])
            self.assertEqual(questions[1]["maps"][0]["overviews"][0]["display_crop"], [0, 0, 256, 240])
            self.assertTrue(account.called)
            model.assert_not_called()
            self.assertNotIn('"label": "Action"', output.getvalue())

    def test_gui_failed_login_does_not_reach_map_or_inference(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); source = root / "corpus"; source.mkdir()
            path = root / "config.json"; initialize(path, source, None)
            incoming = json.dumps({"answer": json.dumps({"kind": "codex", "model": ""})}) + "\n"
            output = io.StringIO()
            with patch("sys.stdin", io.StringIO(incoming)), patch("sys.stdout", output), patch("mhfz_builder.gui_session.ensure_provider", return_value=False), patch("mhfz_builder.wizard.create_plan") as model:
                self.assertEqual(run_gui(path), 0)
            self.assertNotIn('"control": "map"', output.getvalue())
            model.assert_not_called()

    def test_editor_session_reuses_codex_and_failed_validation_returns_to_provider(self):
        for ready in (True, False):
            with self.subTest(ready=ready), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp); source = root / "corpus"; source.mkdir()
                path = root / "config.json"; initialize(path, source, None)
                output = io.StringIO()
                incoming = ''.join(json.dumps({'answer': value}) + '\n' for value in ('again', 'exit')) if ready else ''
                with patch.dict('os.environ', {'MHFZ_EDITOR_CODEX_READY': '1'}), patch('sys.stdin', io.StringIO(incoming)), patch('sys.stdout', output), patch('mhfz_builder.gui_session.ensure_provider', return_value=ready) as account, patch('mhfz_builder.planning.coverage', return_value={'parsed': 1}), patch('mhfz_builder.gui_session.create_quest') as create:
                    self.assertEqual(run_gui(path), 0)
                events = [json.loads(line) for line in output.getvalue().splitlines()]
                controls = [event.get('control') for event in events if event['kind'] == 'question']
                self.assertEqual(controls, ['choice', 'choice'] if ready else ['provider'])
                self.assertEqual(account.call_count, 2 if ready else 1)
                self.assertEqual(create.call_count, 2 if ready else 0)
                self.assertEqual(any(event['kind'] == 'codex-ready' for event in events), ready)


if __name__ == "__main__":
    unittest.main()
