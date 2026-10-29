from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from test_core import fixture
from mhfz_builder.config import initialize
from mhfz_builder.corpus import scan
from mhfz_builder.wizard import Back, Console, create_quest, start


class NavigationCorpusTests(unittest.TestCase):
    def project(self, root):
        source = root / "corpus"; source.mkdir()
        for i in range(4):
            (source / f"{i}.bin").write_bytes(fixture())
        path = root / "quest-builder.local.json"
        return path, initialize(path, source, None)

    def ui(self, answers):
        iterator = iter(answers); messages = []
        return Console(lambda _: next(iterator), messages.append), messages

    def test_back_from_text_and_numeric_prompts(self):
        for value in ("b", "BACK", "indietro", "\x1b"):
            with self.subTest(value=value):
                ui, _ = self.ui([value])
                with self.assertRaises(Back):
                    ui.number("Number", 1, 10)

    def test_back_from_child_settings_returns_to_settings_then_main(self):
        with tempfile.TemporaryDirectory() as tmp:
            path, _ = self.project(Path(tmp))
            ui, messages = self.ui(["4", "2", "b", "0", "5"])
            self.assertEqual(start(path, ui), 0)
            self.assertEqual(sum("Settings / paths, provider and account" in m for m in messages), 2)

    def test_back_from_create_returns_to_main_without_model_requests(self):
        with tempfile.TemporaryDirectory() as tmp:
            path, config = self.project(Path(tmp)); scan(config)
            ui, _ = self.ui(["1", "b", "5"])
            with patch("mhfz_builder.wizard.create_plan") as model:
                self.assertEqual(start(path, ui), 0)
            model.assert_not_called()

    def test_create_back_returns_to_previous_step_before_leaving(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, config = self.project(Path(tmp)); scan(config)
            ui, messages = self.ui(["", "b", "b"])
            with patch("mhfz_builder.wizard.create_plan") as model:
                with self.assertRaises(Back):
                    create_quest(config, ui)
            model.assert_not_called()
            self.assertTrue(any("previous step" in m for m in messages))

    def test_scan_interruption_commits_completed_records_and_resumes(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, config = self.project(Path(tmp))
            def progress(event):
                if event["processed"] == 2:
                    raise Back()
            with self.assertRaises(Back):
                scan(config, progress=progress)
            db = sqlite3.connect(Path(config["workspace"]) / "catalog.sqlite3")
            try:
                self.assertEqual(db.execute("SELECT COUNT(*) FROM quests WHERE status='parsed'").fetchone()[0], 2)
            finally:
                db.close()
            events = []
            result = scan(config, decode=True, progress=events.append)
            self.assertEqual(result["statuses"]["parsed"], 4)
            self.assertEqual(events[-1]["processed"], 4)

    def test_decode_without_limit_attempts_every_compressed_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, config = self.project(Path(tmp))
            for i in range(5):
                (Path(config["source"]) / f"packed{i}.bin").write_bytes(b"JKR" + bytes(20))
            from mhfz_builder.binary import inspect_bytes
            with patch("mhfz_builder.corpus.read_summary", return_value=inspect_bytes(fixture())) as decoder:
                result = scan(config, decode=True)
            self.assertEqual(decoder.call_count, 5)
            self.assertEqual(result["statuses"]["parsed"], 9)
            self.assertTrue(result["coverage_complete"])
