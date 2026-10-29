import copy
import struct
import tempfile
import unittest
from pathlib import Path
from test_core import fixture
from mhfz_builder.config import validate
from mhfz_builder.corpus import scan, search
from mhfz_builder.planning import coverage, references, public_references, validate_intent, validate_plan


def intent():
    return {"monster_ids": [], "map_id": 15, "reference_quest_id": None, "requirements": [], "questions": []}


def plan():
    return {"research_requests": [], "summary": "Tower test", "base_reference_id": "R1", "base_reason": "Map package reference",
            "changes": [{"field": "sub_b", "requested_value": "Damage objective", "evidence_reference_ids": ["R1"], "confidence": "supported"}],
            "questions": [], "warnings": [], "requires_game_test": True}


class PlanTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.source = self.root / "quests"
        self.source.mkdir()
        self.config = validate({"source": str(self.source), "workspace": str(self.root / "work"), "source_kind": "project"})

    def test_no_index_does_not_claim_coverage(self):
        with self.assertRaises(ValueError):
            coverage(self.config)

    def test_numeric_map_filter_does_not_match_digits_in_other_map_names(self):
        for name, map_id in [('a-tower.bin', 13), ('z-siege.bin', 1)]:
            data = bytearray(fixture())
            struct.pack_into('<I', data, 128, map_id)
            (self.source / name).write_bytes(data)
        scan(self.config)
        rows = references(self.config, dict(intent(), map_id=1), limit=1)
        self.assertEqual([r['quest']['map'] for r in rows], [1])
        self.assertEqual([r['quest']['map'] for r in search(self.config, map_filter='1')], [1])
        self.assertEqual([r['quest']['map'] for r in search(self.config, map_filter='Tower')], [13])

    def test_variants_are_preserved_when_reference_hashes_match(self):
        for name in ("65026d0.bin", "65026n0.bin"):
            (self.source / name).write_bytes(fixture())
        (self.source / "packed.bin").write_bytes(b"JKR" + bytes(40))
        scan(self.config)
        rows = references(self.config, intent())
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0]["source_variants"]), 2)
        self.assertFalse(coverage(self.config)["complete"])
        public = public_references(rows)
        self.assertNotIn(str(self.root), str(public))
        self.assertNotIn("texts", public[0]["quest"])
        self.assertEqual(validate_plan(plan(), rows), plan())

    def test_changed_reference_is_rejected(self):
        source = self.source / "quest.bin"
        source.write_bytes(fixture())
        scan(self.config)
        source.write_bytes(b"changed")
        with self.assertRaises(ValueError):
            references(self.config, intent())

    def test_alternative_monsters_match_one_native_species(self):
        for index, monster in enumerate((7, 50, 55, 174)):
            data = bytearray(fixture())
            struct.pack_into('<I', data, 128, 1)
            struct.pack_into('<I', data, 440, monster)
            (self.source / f'{index}.bin').write_bytes(data)
        scan(self.config)
        request = dict(intent(), map_id=1, monster_ids=[7, 50, 55])
        self.assertEqual(references(self.config, request), [])
        rows = references(self.config, dict(request, monster_match='any'))
        self.assertEqual({r['quest']['monsters'][0]['id'] for r in rows}, {7, 50, 55})
        with self.assertRaises(ValueError):
            references(self.config, dict(request, monster_match='unknown'))

    def test_invalid_ids_types_and_extra_fields_are_rejected(self):
        for changes in ({"monster_ids": [99999]}, {"monster_ids": [True]}, {"map_id": 99999}, {"reference_quest_id": 0}, {"extra": "offset patch"}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                validate_intent(dict(intent(), **changes))

    def test_unknown_reference_and_unverified_claims_are_rejected(self):
        rows = [{"reference_id": "R1"}]
        examples = []
        value = plan(); value["base_reference_id"] = "R99"; examples.append(value)
        value = plan(); value["changes"][0]["evidence_reference_ids"] = ["R99"]; examples.append(value)
        value = plan(); value["changes"][0]["evidence_reference_ids"] = []; examples.append(value)
        value = plan(); value["requires_game_test"] = False; examples.append(value)
        value = plan(); value["changes"][0]["field"] = "raw_offset"; examples.append(value)
        for value in examples:
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_plan(value, rows)

    def test_missing_candidate_can_only_produce_a_plan_without_a_base(self):
        value = plan()
        value.update(base_reference_id=None, changes=[], questions=["Decode more references"])
        self.assertEqual(validate_plan(value, []), value)
