import copy
import json
import struct
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from test_core import fixture
from mhfz_builder.binary import inspect_bytes, digest
from mhfz_builder.build_schema import empty_edits
from mhfz_builder.writer import patch_bytes, damage_threshold
from mhfz_builder.config import initialize
from mhfz_builder.build_service import prepare_spec, build, roundtrip, compile_project


def sub_b(edits, quantity=100):
    edits["objectives"] = [{"slot": "sub_b", "kind": "Damage", "target": 174, "quantity_raw": quantity}]
    edits["texts"]["sub_b_objective"] = f"Deal {quantity*100} damage"
    return edits


class WriterTests(unittest.TestCase):
    def test_no_op_preserves_every_unknown_byte(self):
        data = bytearray(fixture())
        data[700:796] = bytes(range(96))
        output, proof = patch_bytes(bytes(data), 65026, empty_edits())
        self.assertEqual(output, bytes(data))
        self.assertEqual(proof["changed_original_offsets"], [])
        self.assertEqual(proof["appended_bytes"], 0)

    def test_new_id_and_objective_preserve_map_spawn_rewards_and_opaque_regions(self):
        original = fixture()
        output, proof = patch_bytes(original, 65027, sub_b(empty_edits()))
        after = inspect_bytes(output)
        before = inspect_bytes(original)
        self.assertEqual(after["quest_id"], 65027)
        self.assertEqual(after["objectives"][2]["damage_points"], 10000)
        self.assertEqual(after["texts"][3], "Deal 10000 damage")
        for name in ("map", "player_stages", "return_stage", "monsters", "rewards", "variants", "quest_flags"):
            self.assertEqual(after[name], before[name])
        allowed = set(range(232,236)) | set(range(238,240)) | set(range(256,264))
        self.assertTrue(set(proof["changed_original_offsets"]).issubset(allowed))
        for i in range(len(original)):
            if i not in allowed:
                self.assertEqual(output[i], original[i])
        self.assertEqual(output[-5:], b"ARCA\0")

    def test_appended_strings_preserve_shared_original_text_and_pointer_table(self):
        data = bytearray(fixture())
        struct.pack_into("<I", data, 564, 600)
        edits = empty_edits(); edits["texts"]["title"] = "A much longer quest title"
        output, _ = patch_bytes(bytes(data), 65026, edits)
        summary = inspect_bytes(output)
        self.assertEqual(summary["texts"][0], "A much longer quest title")
        self.assertEqual(summary["texts"][1], "Test!")
        self.assertEqual(output[560:606], bytes(data[560:606]))
        second, _ = patch_bytes(output, 65026, edits)
        self.assertEqual(second, output)

    def test_fixed_fields_read_back_and_unknown_failure_field_is_preserved(self):
        edits = empty_edits()
        edits.update(time_minutes=20, stat_table=34, variants=[9,0,1,2,3], quest_flags=[1,2,3,4], finish_raw=2)
        output, _ = patch_bytes(fixture(), 65026, edits)
        row = inspect_bytes(output)
        self.assertEqual(row["time_minutes"], 20)
        self.assertEqual(row["stat_table"], 34)
        self.assertEqual(row["variants"], [9,0,1,2,3])
        self.assertEqual(row["failure_value_raw32"], 0x12345678)

    def test_malformed_edits_unsupported_fields_and_text_are_rejected(self):
        examples=[]
        edits=empty_edits(); edits["time_minutes"]=True; examples.append(edits)
        edits=empty_edits(); edits["map"]=15; examples.append(edits)
        edits=empty_edits(); edits["variants"]=[1,2]; examples.append(edits)
        edits=empty_edits(); edits["texts"]["title"]="bad\0text"; examples.append(edits)
        edits=empty_edits(); edits["texts"]["title"]=chr(0x1F409); examples.append(edits)
        edits=sub_b(empty_edits()); edits["texts"]["sub_b_objective"]=None; examples.append(edits)
        edits=sub_b(empty_edits()); edits["objectives"][0]["target"]=150; examples.append(edits)
        edits=sub_b(empty_edits(), 75); examples.append(edits)
        for edits in examples:
            with self.subTest(edits=edits), self.assertRaises(ValueError):
                patch_bytes(fixture(), 65027, edits)

    def test_native_duplicates_are_preserved_when_not_introduced_by_the_build(self):
        data=bytearray(fixture())
        data[256:264]=data[240:248]
        edits=empty_edits()
        edits["objectives"]=[{"slot":"main","kind":"Damage","target":174,"quantity_raw":75}]
        output,_=patch_bytes(bytes(data),65026,edits)
        self.assertEqual(output,bytes(data))

    def test_damage_percent_requires_explicit_rounding_and_does_not_set_hp(self):
        with self.assertRaises(ValueError):
            damage_threshold(13299,"50","exact")
        self.assertEqual(damage_threshold(13299,"50","ceil")["damage_points"],6700)
        self.assertEqual(damage_threshold(13299,"50","floor")["damage_points"],6600)
        self.assertEqual(damage_threshold(30000,"50","exact")["quantity_raw"],150)
        with self.assertRaises(ValueError):
            damage_threshold(30000,"NaN","ceil")


class BuildTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name); self.corpus=self.root/"quests";self.corpus.mkdir()
        self.config=initialize(self.root/"config.local.json",self.corpus,None)
        for role in ("d0","n0"):
            (self.corpus/f"65026{role}.bin").write_bytes(fixture())
        self.spec=prepare_spec(self.config,self.corpus/"65026d0.bin",65027)
        self.destination=Path(self.config["workspace"])/"builds/test"

    def test_export_preserves_both_variants_and_hash_backups(self):
        self.spec["edits"]=sub_b(empty_edits())
        report=build(self.config,self.spec,self.destination)
        self.assertEqual(len(report["outputs"]),2)
        manifest=json.loads(Path(report["manifest"]).read_text())
        for row in manifest["outputs"]:
            self.assertEqual(digest(Path(row["source_backup"]).read_bytes()),row["source"]["sha256"])
            self.assertEqual(inspect_bytes(Path(row["path"]).read_bytes())["quest_id"],65027)
        self.assertEqual((self.corpus/"65026d0.bin").read_bytes(),fixture())
        self.assertFalse(manifest["installed"])
        self.assertFalse(manifest["database_id_checked"])
        with self.assertRaises(ValueError):
            build(self.config,self.spec,self.destination)

    def test_low_ids_use_five_digit_server_filenames(self):
        self.spec["quest_id"]=1
        result=build(self.config,self.spec,self.destination)
        self.assertEqual({Path(p).name for p in result["outputs"]},{"00001d0.bin","00001n0.bin"})
        self.assertEqual(inspect_bytes(Path(result["outputs"][0]).read_bytes())["quest_id"],1)

    def test_dry_run_produces_no_build_or_source_backup_files(self):
        report=build(self.config,self.spec,self.destination,dry_run=True)
        self.assertEqual(report["status"],"validated_not_written")
        self.assertFalse(self.destination.exists())
        self.assertFalse((Path(self.config["workspace"])/"source-backups").exists())

    def test_stale_source_unresolved_decisions_and_invalid_destination_stop_before_export(self):
        for key in ("unresolved","unsupported"):
            bad=copy.deepcopy(self.spec);bad[key]=["missing decision"]
            with self.assertRaises(ValueError):build(self.config,bad,self.destination)
        with self.assertRaises(ValueError):build(self.config,self.spec,self.corpus/"output")
        bad=copy.deepcopy(self.spec);bad["sources"][0]["role"]="../escape"
        with self.assertRaises(ValueError):build(self.config,bad,self.destination)
        (self.corpus/"65026n0.bin").write_bytes(b"changed")
        with self.assertRaises(ValueError):build(self.config,self.spec,self.destination)
        self.assertFalse(self.destination.exists())

    def test_target_id_occupancy_is_checked_in_the_corpus(self):
        (self.corpus/"65027d0.bin").write_bytes(fixture())
        with self.assertRaises(ValueError):build(self.config,self.spec,self.destination)
        self.assertFalse(self.destination.exists())

    def test_compressed_roundtrip_compares_the_decoded_payload_and_preserves_container(self):
        packed=self.corpus/"65026d0.bin";packed.write_bytes(b"JKR"+bytes(20))
        raw=self.root/"decoded.bin";raw.write_bytes(fixture())
        original=packed.read_bytes()
        with patch("mhfz_builder.build_service.unpack",return_value={"quest_files":[str(raw)]}):
            result=roundtrip(self.config,packed)
        self.assertTrue(result["raw_byte_identical"])
        self.assertEqual(packed.read_bytes(),original)

    def test_typed_compiler_is_bound_to_the_selected_base_and_requested_id(self):
        from mhfz_builder.binary import inspect_bytes
        source=self.corpus/"65026d0.bin"
        reference={"reference_id":"R1","source_variants":[str(source.resolve())],"source_sha256":digest(fixture()),"quest":inspect_bytes(fixture())}
        proposal={"summary":"test","base_reference_id":"R1","base_reason":"template","changes":[],"questions":[],"warnings":[],"requires_game_test":True}
        project={"prompt":"test","references":[reference],"plan":proposal}
        class Client:
            calls=[]
            def request(self,*args):return {"base_reference_id":"R1","quest_id":65027,"edits":sub_b(empty_edits()),"unresolved":[],"unsupported":[],"warnings":["Client test still required"]}
        spec=compile_project(self.config,project,"project-hash",65027,"10000 damage",Client())
        self.assertEqual(len(spec["sources"]),2)
        self.assertEqual(spec["edits"]["objectives"][0]["quantity_raw"],100)
        class WrongClient(Client):
            def request(self,*args):
                value=super().request(*args);value["quest_id"]=65028;return value
        with self.assertRaises(ValueError):compile_project(self.config,project,"hash",65027,"",WrongClient())
