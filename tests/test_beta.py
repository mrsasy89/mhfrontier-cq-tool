import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile
from test_core import fixture
from mhfz_builder import __version__
from mhfz_builder.binary import digest
from mhfz_builder.config import initialize, load
from mhfz_builder.corpus import scan
from mhfz_builder.build_service import prepare_spec, build
from mhfz_builder.registration import export_registration
from mhfz_builder.wizard import Console, start, create_quest, configure_paths, index_ready

ROOT = Path(__file__).resolve().parents[1]


class BetaTests(unittest.TestCase):
    def setup_project(self, root):
        source = root / "corpus"; source.mkdir()
        (source / "65026d0.bin").write_bytes(fixture())
        config_path = root / "quest-builder.local.json"
        config = initialize(config_path, source, None)
        return config_path, config

    def console(self, answers):
        answers = iter(answers)
        messages = []
        return Console(lambda _: next(answers), messages.append), messages

    def test_guided_first_setup_and_exit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ui, messages = self.console(["y", "project", str(root / "corpus"), "", "", "5"])
            self.assertEqual(start(root / "quest-builder.local.json", ui), 0)
            self.assertEqual(load(root / "quest-builder.local.json")["source_kind"], "project")
            self.assertTrue(any("Configuration created" in m for m in messages))

    def test_invalid_type_does_not_create_corpus(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); ui, _ = self.console(["typo"])
            with self.assertRaises(ValueError):
                configure_paths(root / "quest-builder.local.json", ui)
            self.assertFalse((root / "corpus").exists())

    def test_path_update_preserves_original_config_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path, config = self.setup_project(Path(tmp)); original = path.read_bytes()
            ui, _ = self.console(["", "", "", ""])
            configure_paths(path, ui)
            backup = Path(config["workspace"]) / "config-backups" / (digest(original) + ".json")
            self.assertEqual(backup.read_bytes(), original)

    def test_changed_corpus_requires_reindex(self):
        with tempfile.TemporaryDirectory() as tmp:
            path, config = self.setup_project(Path(tmp)); scan(config)
            self.assertEqual(index_ready(config)["parsed"], 1)
            other = Path(tmp) / "other"; other.mkdir()
            with self.assertRaisesRegex(ValueError, "another corpus"):
                index_ready(dict(config, source=str(other.resolve())))

    def test_guided_preview_can_save_without_building(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, config = self.setup_project(Path(tmp)); scan(config)
            project = {"plan": {"summary": "Test", "questions": []}, "references": [], "status": "needs_review"}
            spec = {"unresolved": [], "unsupported": [], "edits": {}, "provenance": {}}
            ui, messages = self.console(["", "Create a test", "50 minutes", "Keep native rewards", "END", "", "", "", "", "65027", "yes", "", "0"])
            with patch("mhfz_builder.wizard.ensure_provider", return_value=True), patch("mhfz_builder.wizard.create_plan", return_value=project) as planner, patch("mhfz_builder.wizard.create_client"), patch("mhfz_builder.wizard.compile_project", return_value=spec), patch("mhfz_builder.wizard.build") as writer:
                create_quest(config, ui)
            writer.assert_not_called()
            self.assertTrue(planner.call_args.args[1].startswith("Create a test\n50 minutes\nKeep native rewards"))
            sessions = list((Path(config["workspace"]) / "sessions").iterdir())
            self.assertTrue((sessions[0] / "plan.json").is_file())
            self.assertTrue((sessions[0] / "spec-1.json").is_file())

    def test_registration_checks_real_build_and_never_overwrites(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, config = self.setup_project(Path(tmp))
            spec = prepare_spec(config, Path(config["source"]) / "65026d0.bin", 65027)
            result = build(config, spec, Path(config["workspace"]) / "build")
            registration = export_registration(config, result["manifest"])
            self.assertFalse(registration["executed"])
            self.assertIn("SELECT 65027,54,4,0,9", Path(registration["saved"]).read_text())
            with self.assertRaises(FileExistsError):
                export_registration(config, result["manifest"])
            Path(result["outputs"][0]).write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "hash/path"):
                export_registration(config, result["manifest"])
            with self.assertRaisesRegex(ValueError, "workspace"):
                export_registration(config, Path(tmp) / "outside.json")

    def test_guided_flow_exports_all_variants_and_sql(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, config = self.setup_project(Path(tmp))
            source = Path(config["source"]) / "65026d0.bin"
            (source.parent / "65026n0.bin").write_bytes(source.read_bytes())
            scan(config)
            spec = prepare_spec(config, source, 65027)
            project = {"plan": {"summary": "Test", "questions": ["Keep rewards?"]},
                       "references": [{"reference_id": "R1", "quest": {"quest_id": 65026, "map_name": "Test"}, "source_variants": [str(source)]}],
                       "status": "needs_review"}
            ui, _ = self.console(["", "Use this native map", "END", "", "", "", "", "65027", "yes", "Keep rewards", "1", "y", "", "", ""])
            with patch("mhfz_builder.wizard.ensure_provider", return_value=True), patch("mhfz_builder.wizard.create_plan", return_value=project), patch("mhfz_builder.wizard.create_client"), patch("mhfz_builder.wizard.compile_project", return_value=spec):
                create_quest(config, ui)
            session = next((Path(config["workspace"]) / "sessions").iterdir())
            output = Path(config["workspace"]) / "custom-quests" / session.name
            self.assertTrue((output / "65027d0.bin").is_file())
            self.assertTrue((output / "65027n0.bin").is_file())
            self.assertTrue((output / "register-event-quest.sql").is_file())
            self.assertEqual(source.read_bytes(), fixture())

    def test_distribution_runs_without_checkout_and_excludes_private_data(self):
        spec = importlib.util.spec_from_file_location("package_beta", ROOT / "scripts/package_beta.py")
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); distribution = root / "distribution"
            module.package(distribution)
            app = distribution / "quest-builder.pyz"
            with zipfile.ZipFile(app) as archive:
                names = archive.namelist()
                self.assertIn("mhfz_builder/data/catalog.json", names)
                self.assertFalse(any(".workspace" in n or n.endswith(".bin") or "local.json" in n for n in names))
            result = subprocess.run([sys.executable, str(app), "--version"], cwd=root, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), __version__)
            # Exercise resource loading and a complete packaged menu without a model request.
            self.setup_project(root)
            result = subprocess.run([sys.executable, str(app), "start"], cwd=root, input="5\n", capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Create quest from prompt", result.stdout)
            with self.assertRaises(FileExistsError):
                module.package(distribution)
