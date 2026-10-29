import json
import struct
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import subprocess
from mhfz_builder.binary import inspect_bytes, digest
from mhfz_builder.config import initialize, validate
from mhfz_builder.corpus import scan, search
from mhfz_builder.refrontier import unpack
from mhfz_builder.cli import export_sql, main


def fixture():
    data = bytearray(800)
    def put(fmt, offset, *args):
        struct.pack_into(fmt, data, offset, *args)
    put("<I", 0, 192)
    put("<I", 4, 112)
    put("<I", 52, 128)
    put("<I", 112, 129)
    put("<I", 36, 128)
    put("<II", 128, 15, 121)
    put("<I", 24, 144)
    put("<I", 156, 440)
    put("<III", 440, 174, 1, 128)
    put("<3f", 472, 13953, 0, 13844)
    put("<H", 500, 65535)
    put("<I", 12, 512)
    put("<BBHI", 512, 0, 128, 0, 536)
    put("<H", 520, 65535)
    put("<3H", 536, 100, 25, 2)
    put("<H", 542, 65535)
    put("<I", 232, 560)
    put("<I", 560, 600)
    data[600:606] = b"Test!\0"
    put("<H", 238, 65026)
    put("<IBBH", 240, 32772, 174, 0, 75)
    put("<I", 224, 50 * 1800)
    put("<I", 212, 0x12345678)
    data[337], data[338], data[374], data[375], data[376] = 9, 0, 3, 4, 5
    return bytes(data)


class BinaryTests(unittest.TestCase):
    def test_reads_structure_and_preserves_unknowns(self):
        row = inspect_bytes(fixture())
        self.assertEqual(row["quest_id"], 65026)
        self.assertEqual(row["objectives"][0]["damage_points"], 7500)
        self.assertEqual(row["variants"], [9, 0, 3, 4, 5])
        self.assertEqual(row["failure_value_raw32"], 0x12345678)
        self.assertEqual(row["monsters"][0]["stage"], 128)
        self.assertEqual(row["rewards"][0]["header_unknown0"], 128)
        self.assertEqual(row["texts"][1], "")
        self.assertFalse(row["runtime_verified"])

    def test_bad_pointer_rejected(self):
        data = bytearray(fixture())
        struct.pack_into("<I", data, 36, 999999)
        with self.assertRaises(ValueError):
            inspect_bytes(data)

    def test_truncated_or_packed_rejected(self):
        for data in (b"", b"JKR" + bytes(500), fixture()[:250]):
            with self.subTest(length=len(data)), self.assertRaises(ValueError):
                inspect_bytes(data)


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "corpus"
        self.source.mkdir()
        self.config = validate({"source": str(self.source), "workspace": str(self.root / "work"), "source_kind": "project"})

    def test_nested_workspace_rejected(self):
        for workspace in (self.source, self.source / "work", self.root):
            with self.subTest(workspace=workspace), self.assertRaises(ValueError):
                validate(dict(self.config, workspace=str(workspace)))

    def test_config_cannot_be_written_inside_corpus(self):
        path = self.source / "settings.local.json"
        with self.assertRaises(ValueError):
            initialize(path, self.source, None, workspace=self.root / "work")
        self.assertFalse(path.exists())

    def test_decode_timeout_is_recorded_and_scan_continues(self):
        (self.source / "a.bin").write_bytes(b"JKR" + bytes(50))
        (self.source / "b.bin").write_bytes(fixture())
        with patch("mhfz_builder.corpus.read_summary", side_effect=subprocess.TimeoutExpired("tool", 120)):
            report = scan(self.config, decode=True)
        self.assertEqual(report["statuses"], {"error": 1, "parsed": 1})

    def test_config_does_not_overwrite(self):
        path = self.root / "settings.local.json"
        initialize(path, self.source, None)
        before = path.read_bytes()
        with self.assertRaises(ValueError):
            initialize(path, self.source, None)
        self.assertEqual(before, path.read_bytes())

    def test_inventory_keeps_variants_errors_and_packed(self):
        for name in ("65026d0.bin", "65026n0.bin"):
            (self.source / name).write_bytes(fixture())
        (self.source / "bad.bin").write_bytes(b"bad")
        (self.source / "packed.bin").write_bytes(b"JKR" + bytes(50))
        report = scan(self.config)
        self.assertEqual(report["found_bin_files"], 4)
        self.assertEqual(report["statuses"], {"error": 1, "needs_decode": 1, "parsed": 2})
        self.assertFalse(report["coverage_complete"])
        self.assertEqual(len(search(self.config, map_filter="15")), 2)
        (self.source / "65026n0.bin").unlink()
        self.assertEqual(scan(self.config)["statuses"]["missing"], 1)
        self.assertEqual(len(search(self.config)), 1)
        (self.source / "65026d0.bin").write_bytes(b"changed")
        self.assertEqual(len(search_after_scan(self.config)), 0)

    def test_unpack_tool_receives_copy_and_cache_detects_changes(self):
        original = self.source / "packed.bin"
        original.write_bytes(b"JKR" + bytes(50))
        original_hash = digest(original.read_bytes())
        def run(args, **kwargs):
            Path(args[1]).write_bytes(fixture())
            return subprocess.CompletedProcess(args, 0, "decoded", "")
        with patch("mhfz_builder.refrontier.probe", return_value={"mode": "legacy"}), patch("mhfz_builder.refrontier.subprocess.run", side_effect=run) as call:
            report = unpack(self.config, original)
            self.assertEqual(digest(original.read_bytes()), original_hash)
            self.assertNotEqual(Path(call.call_args.args[0][1]), original)
            self.assertEqual(unpack(self.config, original), report)
            self.assertEqual(call.call_count, 1)
            Path(report["quest_files"][0]).write_bytes(b"manual edit")
            with self.assertRaises(ValueError):
                unpack(self.config, original)

    def test_sql_validated_and_not_executed(self):
        self.assertIn("WHERE NOT EXISTS", export_sql(65026, 54, 4, 9))
        for values in ((0, 54, 4, 9), (65026, 54, 0, 9), (65026, 54, 4, 256)):
            with self.assertRaises(ValueError):
                export_sql(*values)


def search_after_scan(config):
    scan(config)
    return search(config)


if __name__ == "__main__":
    unittest.main()
