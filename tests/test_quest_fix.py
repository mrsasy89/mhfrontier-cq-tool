import json
from pathlib import Path
import struct
import tempfile
import unittest
from test_core import fixture
from mhfz_builder.binary import inspect_bytes
from mhfz_builder.config import initialize
from mhfz_builder.quest_fix import diagnose_summary, run


class QuestFixTests(unittest.TestCase):
    def data(self, reward=22500, penalty=3, g=False, quest=65026):
        data = bytearray(fixture())
        struct.pack_into("<II", data, 208, reward, penalty)
        struct.pack_into("<H", data, 238, quest)
        data[343] = 8 if g else 0
        data[345] = 32
        return bytes(data)

    def setup_case(self, root, data):
        source = root / "corpus"; source.mkdir()
        quest = inspect_bytes(data)["quest_id"]
        path = source / f"{quest}d0.bin"; path.write_bytes(data)
        (source / f"{quest}n0.bin").write_bytes(data)
        config = initialize(root / "config.local.json", source, None)
        return config, path

    def test_76_display_is_conditional_not_verified(self):
        report = diagnose_summary(inspect_bytes(self.data()))
        self.assertEqual(report["hypotheses"][0]["display_wrap_example"], 76)
        self.assertEqual(report["hypotheses"][0]["suggested_penalty_u32"], 7500)
        self.assertFalse(report["runtime_verified"])
        self.assertTrue(report["facts"]["interception_diva_bit_present"])

    def test_diagnosis_never_exports_bins_or_changes_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); original = self.data(); config, path = self.setup_case(root, original)
            folder = Path(config["workspace"]) / "diagnosis"
            result = run(config, path, folder)
            self.assertEqual(result["variants"], 2)
            self.assertEqual(list(folder.glob("*.bin")), [])
            self.assertEqual(path.read_bytes(), original)
            with self.assertRaisesRegex(ValueError, "already exists"):
                run(config, path, folder)

    def test_hr_candidate_is_full_u32_and_preserves_every_other_byte(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); original = self.data(penalty=3); config, path = self.setup_case(root, original)
            folder = Path(config["workspace"]) / "candidate"
            run(config, path, folder, mode="hr-penalty")
            for role in ("d0", "n0"):
                output = (folder / f"65026{role}.bin").read_bytes()
                self.assertEqual(struct.unpack_from("<I", output, 212)[0], 7500)
                self.assertEqual(output[:212], original[:212])
                self.assertEqual(output[216:], original[216:])
            self.assertEqual(path.read_bytes(), original)
            self.assertTrue(json.loads((folder / "quest-fix-report.json").read_text())["variants"][0]["candidate"]["source_backup"])

    def test_preserves_different_but_correct_third_faint_penalty(self):
        with tempfile.TemporaryDirectory() as tmp:
            config, path = self.setup_case(Path(tmp), self.data(penalty=8000))
            folder = Path(config["workspace"]) / "correct"
            run(config, path, folder, mode="hr-penalty")
            self.assertEqual((folder / path.name).read_bytes(), path.read_bytes())

    def test_g_profile_is_explicit_and_cannot_apply_hr_arithmetic(self):
        with tempfile.TemporaryDirectory() as tmp:
            config, path = self.setup_case(Path(tmp), self.data(g=True, penalty=9))
            folder = Path(config["workspace"]) / "g"
            with self.assertRaisesRegex(ValueError, "conflicts"):
                run(config, path, folder, mode="hr-penalty")
            self.assertFalse(folder.exists())
            run(config, path, folder, mode="g-carts")
            self.assertEqual(inspect_bytes((folder / path.name).read_bytes())["failure_value_raw32"], 3)

    def test_protected_65005_can_be_diagnosed_but_not_edited(self):
        with tempfile.TemporaryDirectory() as tmp:
            config, path = self.setup_case(Path(tmp), self.data(quest=65005))
            folder = Path(config["workspace"]) / "protected"
            run(config, path, folder)
            with self.assertRaisesRegex(ValueError, "protected"):
                run(config, path, folder.parent / "edit", mode="hr-penalty")

    def test_zero_reward_and_unrepresentable_counts_refuse_candidate(self):
        for reward in (0, 4):
            with self.subTest(reward=reward), tempfile.TemporaryDirectory() as tmp:
                config, path = self.setup_case(Path(tmp), self.data(reward=reward))
                with self.assertRaises(ValueError):
                    run(config, path, Path(config["workspace"]) / "bad", mode="hr-penalty")

    def test_refuses_corpus_destination_and_reports_reward_total(self):
        with tempfile.TemporaryDirectory() as tmp:
            config, path = self.setup_case(Path(tmp), self.data())
            with self.assertRaisesRegex(ValueError, "workspace"):
                run(config, path, path.parent / "bad")
            summary = inspect_bytes(path.read_bytes()); summary["rewards"][0]["rate_total"] = 110
            self.assertEqual(diagnose_summary(summary)["reward_table_warnings"][0]["configured_rate_total"], 110)
