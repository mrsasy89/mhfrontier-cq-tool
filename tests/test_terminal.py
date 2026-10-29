from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from mhfz_builder.config import load
from mhfz_builder.wizard import Console, configure_paths


class TerminalTests(unittest.TestCase):
    def test_cls_redraws_current_menu_without_becoming_an_integer_error(self):
        answers = iter(["cls", "4"]); messages = []
        ui = Console(lambda _: next(answers), messages.append)
        with patch.object(ui, "clear") as clear:
            ui.screen("Main menu", "1. Create\n4. Settings")
            self.assertEqual(ui.number("Action", 1, 6), 4)
        self.assertEqual(clear.call_count, 2)
        self.assertEqual(messages.count("1. Create\n4. Settings"), 2)
        self.assertFalse(any("Enter an integer" in m for m in messages))

    def test_redirected_console_does_not_clear_or_pause(self):
        ui = Console(lambda _: self.fail("Unexpected input"), lambda _: None)
        with patch("mhfz_builder.wizard.subprocess.run") as command:
            ui.clear(); ui.pause()
        command.assert_not_called()

    def test_interactive_results_wait_for_user(self):
        prompts = []; ui = Console(lambda p: prompts.append(p), lambda _: None, interactive=True)
        ui.pause()
        self.assertIn("Press Enter", prompts[0])

    def test_bad_paths_retry_the_current_step_instead_of_restarting_setup(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); source = root / "quests"; source.mkdir()
            tool = root / "ReFrontier.exe"; tool.write_bytes(b"fixture; never executed")
            answers = iter(["server", str(root / "missing"), str(source), str(root / "ReFrontier.ex"), str(tool), ""])
            messages = []
            configure_paths(root / "quest-builder.local.json", Console(lambda _: next(answers), messages.append))
            config = load(root / "quest-builder.local.json")
            self.assertEqual(Path(config["refrontier"]), tool.resolve())
            self.assertEqual(Path(config["source"]), source.resolve())
            self.assertTrue(any("Folder not found" in m for m in messages))
            self.assertTrue(any("Executable not found" in m for m in messages))
