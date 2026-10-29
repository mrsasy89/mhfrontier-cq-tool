from pathlib import Path
import tempfile
import unittest

from mhfz_builder.quest_ids import occupied_ids, first_available
from mhfz_builder.wizard import Console, Back, choose_quest_id


class QuestIdTests(unittest.TestCase):
    def setup_case(self, root):
        source = root / "library"; source.mkdir()
        server = root / "server"; server.mkdir()
        return {"source": str(source), "source_kind": "project",
                "workspace": str(root / "workspace"), "server_quest_directory": str(server)}

    def console(self, answers):
        iterator = iter(answers); messages = []
        return Console(lambda _: next(iterator), messages.append), messages

    def test_scan_all_variants_sources_and_exports_without_decoding(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = self.setup_case(Path(tmp))
            server = Path(config["server_quest_directory"])
            (server / "65001N7.BIN").write_bytes(b"packed")
            (Path(config["source"]) / "65002d0.bin").write_bytes(b"packed")
            output = Path(config["workspace"]) / "custom-quests" / "old-session"
            output.mkdir(parents=True)
            (output / "65003d1.bin").write_bytes(b"packed")
            used, roots, server_checked = occupied_ids(config)
            self.assertEqual(first_available(used), 65004)
            self.assertIn(65005, used)
            self.assertEqual(len(roots), 3)
            self.assertTrue(server_checked)
            self.assertEqual((server / "65001N7.BIN").read_bytes(), b"packed")

    def test_confirmation_is_explicit_and_override_is_confirmed(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = self.setup_case(Path(tmp))
            (Path(config["server_quest_directory"]) / "65002d0.bin").touch()
            ui, messages = self.console(["", "Duration 50 minutes", "65002", "65005", "65027", "yes"])
            self.assertEqual(choose_quest_id(config, ui), 65027)
            self.assertTrue(any("NOT checked" in m for m in messages))
            self.assertTrue(any("Proposed quest ID: 65001" in m for m in messages))

    def test_recheck_catches_new_file_before_confirmation(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = self.setup_case(Path(tmp))
            calls = 0
            def answer(_):
                nonlocal calls
                calls += 1
                if calls == 1:
                    (Path(config["server_quest_directory"]) / "65001d0.bin").touch()
                return "yes"
            self.assertEqual(choose_quest_id(config, Console(answer, lambda _: None)), 65002)

    def test_missing_configured_server_fails_and_no_server_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = self.setup_case(Path(tmp))
            config["server_quest_directory"] += "/missing"
            with self.assertRaisesRegex(ValueError, "directory not found"):
                occupied_ids(config)
            del config["server_quest_directory"]
            ui, messages = self.console(["yes"])
            self.assertEqual(choose_quest_id(config, ui), 65001)
            self.assertTrue(any("No server folder configured" in m for m in messages))

    def test_exhaustion_and_back(self):
        with self.assertRaisesRegex(ValueError, "No free custom"):
            first_available(set(range(65001, 65536)))
        with tempfile.TemporaryDirectory() as tmp:
            ui, _ = self.console(["b"])
            with self.assertRaises(Back):
                choose_quest_id(self.setup_case(Path(tmp)), ui)

    def test_multiline_description_preserves_paragraphs_and_next_answer(self):
        ui, _ = self.console(["HR Kuarusepusu", "50 minutes", "", "Title: Thunder Above the Forest", "END", "yes"])
        self.assertEqual(ui.description(), "HR Kuarusepusu\n50 minutes\n\nTitle: Thunder Above the Forest")
        self.assertEqual(ui.ask("Confirm"), "yes")
        ui, _ = self.console(["END"])
        self.assertEqual(ui.description("Previous text"), "Previous text")


if __name__ == "__main__":
    unittest.main()
