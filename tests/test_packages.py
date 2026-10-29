import copy
import json
import struct
import tempfile
import unittest
from pathlib import Path

from test_core import fixture
from mhfz_builder.binary import Reader, inspect_bytes, digest
from mhfz_builder.build_schema import empty_edits
from mhfz_builder.build_service import build, prepare_spec, source_record, compile_project
from mhfz_builder.config import initialize
from mhfz_builder.corpus import scan
from mhfz_builder.items import mentioned_items
from mhfz_builder.packages import spawn_record
from mhfz_builder.pipeline import create_plan
from mhfz_builder.writer import patch_bytes


def donor(monster=150, stage=123, map_id=15):
    raw = bytearray(fixture())
    struct.pack_into('<I', raw, 128, map_id)
    raw[440] = monster
    struct.pack_into('<I', raw, 448, stage)
    struct.pack_into('<3f', raw, 472, 120.5, -20.0, 600.0)
    raw[452:468] = bytes(range(16))
    return bytes(raw)


def spawn(reference, index=0, position=None):
    return {'reference_id': reference, 'spawn_index': index,
            'position_reference_id': position, 'position_spawn_index': 0 if position else None}


class PackageTests(unittest.TestCase):
    def test_spawn_placement_copies_only_position_and_preserves_opaque_fields(self):
        base = fixture(); position = donor()
        edits = empty_edits(); edits['monster_spawns'] = [spawn('base', position='terrain')]
        result, proof = patch_bytes(base, 65027, edits, {'base': base, 'terrain': position})
        before = spawn_record(base, 0)[0]; after = spawn_record(result, 0)[0]
        expected = bytearray(before); expected[8:12] = position[448:452]; expected[28:44] = position[468:484]
        self.assertEqual(after, bytes(expected))
        self.assertEqual(result[128:144], base[128:144])
        self.assertEqual(inspect_bytes(result)['monsters'][0]['stage'], 123)
        self.assertEqual(inspect_bytes(result)['rewards'], inspect_bytes(base)['rewards'])
        self.assertTrue(any('Cross-species' in note for note in proof['warnings']))
        allowed = {24,25,26,27,238,239}
        self.assertTrue(set(proof['changed_original_offsets']).issubset(allowed))
        # Original native records remain byte-identical and reachable by their old addresses.
        self.assertEqual(result[440:502], base[440:502])

    def test_new_roster_rebuilds_id_list_and_terminators(self):
        edits = empty_edits(); edits['monster_spawns'] = [spawn('base'), spawn('new')]
        result, _ = patch_bytes(fixture(), 65027, edits, {'base': fixture(), 'new': donor()})
        r = Reader(result); header = r.u32(24); ids = r.u32(header + 8)
        self.assertEqual(r.read('<3I', ids), (174,150,0xffffffff))
        records = r.u32(header + 12)
        self.assertEqual(r.u16(records + 120), 65535)
        self.assertEqual([m['id'] for m in inspect_bytes(result)['monsters']], [174,150])

    def test_wrong_map_unknown_evidence_and_invalid_coordinates_stop_writes(self):
        edits = empty_edits(); edits['monster_spawns'] = [spawn('base', position='terrain')]
        bad = bytearray(donor()); struct.pack_into('<f', bad, 472, float('nan'))
        for sources in ({'base': fixture()}, {'base':fixture(), 'terrain':donor(map_id=3)}, {'base':fixture(),'terrain':bytes(bad)}):
            with self.subTest(sources=list(sources)), self.assertRaises(ValueError):
                patch_bytes(fixture(), 65027, edits, sources)

    def test_rewards_append_tables_preserve_native_headers_and_unnamed_tables(self):
        base = bytearray(fixture()); struct.pack_into('<BBH', base, 512, 1, 128, 37)
        edits = empty_edits(); edits['rewards'] = [
            {'table':1,'rows':[{'item':11458,'amount':15,'rate':40}, {'item':11459,'amount':3,'rate':50}]},
            {'table':2,'rows':[{'item':10578,'amount':5,'rate':100}]}]
        result, proof = patch_bytes(bytes(base), 65027, edits)
        tables = inspect_bytes(result)['rewards']
        self.assertEqual(tables[0]['header_unknown1'], 37)
        self.assertEqual(tables[0]['rate_total'], 90)
        self.assertEqual(tables[1]['header_unknown0'], 128)
        self.assertEqual(result[512:544], bytes(base[512:544]))
        self.assertTrue(any('90' in note for note in proof['warnings']))
        only_sub = empty_edits(); only_sub['rewards'] = [edits['rewards'][1]]
        output, _ = patch_bytes(bytes(base), 65027, only_sub)
        self.assertEqual(inspect_bytes(output)['rewards'][0], inspect_bytes(bytes(base))['rewards'][0])

    def test_invalid_reward_ids_sentinel_weights_and_duplicate_tables_rejected(self):
        for item, rate in ((65535,100),(64000,100),(11458,65535),(11458,0)):
            edits=empty_edits(); edits['rewards']=[{'table':1,'rows':[{'item':item,'amount':1,'rate':rate}]}]
            with self.subTest(item=item,rate=rate), self.assertRaises(ValueError):
                patch_bytes(fixture(),65027,edits)
        edits=empty_edits(); table={'table':1,'rows':[{'item':11458,'amount':1,'rate':100}]}; edits['rewards']=[table,table]
        with self.assertRaises(ValueError): patch_bytes(fixture(),65027,edits)

    def test_new_aggregate_main_and_individual_subquests(self):
        edits = empty_edits(); edits['monster_spawns'] = [spawn('base'),spawn('new')]
        edits['objectives'] = [
            {'slot':'main','kind':'Slay_All','target':0,'quantity_raw':1},
            {'slot':'sub_a','kind':'Slay','target':174,'quantity_raw':1},
            {'slot':'sub_b','kind':'Slay','target':150,'quantity_raw':1}]
        edits['texts'].update(main_objective='Slay both monsters',sub_a_objective='Slay Toa',sub_b_objective='Slay second target')
        edits['finish_raw']=2
        result,_=patch_bytes(fixture(),65027,edits,{'base':fixture(),'new':donor()})
        self.assertEqual([o['type'] for o in inspect_bytes(result)['objectives']], [262144,513,513])
        edits['objectives'][0]['quantity_raw']=2
        with self.assertRaisesRegex(ValueError,'quantity_raw=1'):
            patch_bytes(fixture(),65027,edits,{'base':fixture(),'new':donor()})

    def test_removed_boss_cannot_leave_a_stale_objective(self):
        edits=empty_edits(); edits['monster_spawns']=[spawn('new')]
        with self.assertRaisesRegex(ValueError,'removed'):
            patch_bytes(fixture(),65027,edits,{'new':donor()})

    def test_item_names_resolve_from_portable_metadata(self):
        rows=mentioned_items('Gamboge Jewel, Patina Jewel, Ebony Jewel, Gentiana Jewel, Poborubarumu Hide and Varusa Shell')
        self.assertTrue({11458,11459,11460,11461,10578,11183}.issubset({r['item'] for r in rows}))


class EngineIntegrationTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.root=Path(temp.name); self.corpus=self.root/'corpus'; self.corpus.mkdir()
        self.config=initialize(self.root/'config.json',self.corpus,None)
        self.base=self.corpus/'65026d0.bin'; self.base.write_bytes(fixture())
        self.other=self.corpus/'20001d0.bin'; self.other.write_bytes(donor())
        # The donor's internal ID must agree with its physical role when used as a base.
        data=bytearray(self.other.read_bytes()); struct.pack_into('<H',data,238,20001); self.other.write_bytes(data)
        scan(self.config)

    def test_export_hash_binds_and_backs_up_position_evidence(self):
        spec=prepare_spec(self.config,self.base,65027)
        spec['edits']['monster_spawns']=[spawn('base',position='terrain')]
        spec['provenance']['spawn_sources']=[{'reference_id':'base','source':source_record(self.config,self.base)}, {'reference_id':'terrain','source':source_record(self.config,self.other)}]
        before=self.base.read_bytes(); other=self.other.read_bytes()
        report=build(self.config,spec,self.root/'.workspace'/'output')
        manifest=json.loads(Path(report['manifest']).read_text())
        self.assertEqual(len(manifest['evidence_sources']),2)
        for row in manifest['evidence_sources']:
            self.assertEqual(digest(Path(row['backup']).read_bytes()),row['source']['sha256'])
        self.assertEqual(self.base.read_bytes(),before); self.assertEqual(self.other.read_bytes(),other)
        self.other.write_bytes(b'changed')
        with self.assertRaises(ValueError): build(self.config,spec,self.root/'.workspace'/'stale')
        self.assertFalse((self.root/'.workspace'/'stale').exists())

    def test_complementary_research_and_model_requested_item_lookup(self):
        class Client:
            calls=[]
            def __init__(client): client.turn=0
            def request(client,purpose,schema,data):
                if purpose=='quest_intent':
                    return {'monster_ids':[174,150],'map_id':15,'spawn_stage':123,'monster_match':'all','reference_quest_id':None,'requirements':[],'questions':[]}
                client.turn+=1
                value={'summary':'Two targets','base_reference_id':data['references'][0]['reference_id'],'base_reason':'Map package','changes':[],'questions':[],'warnings':[],'requires_game_test':True,'research_requests':[]}
                if client.turn==1:
                    value['research_requests']=[{'kind':'items','monster_id':None,'map_id':None,'stage':None,'quest_id':None,'text':'Varusa'}]
                else:
                    self.assertTrue(data['research_results'][0]['results'][0]['items'])
                return value
        project=create_plan(self.config,'Two monsters in Tower area 2',Client())
        self.assertEqual(len(project['research_log']),1)
        self.assertTrue({174,150}.issubset({m['id'] for r in project['references'] for m in r['quest']['monsters']}))

    def test_compiler_corrects_invalid_output_and_retains_validation_feedback(self):
        ref={'reference_id':'R1','source_variants':[str(self.base)],'source_sha256':digest(self.base.read_bytes()),'quest':inspect_bytes(self.base.read_bytes())}
        proposal={'summary':'test','base_reference_id':'R1','base_reason':'native','changes':[],'questions':[],'warnings':[],'requires_game_test':True}
        project={'prompt':'Rename quest','references':[ref],'plan':proposal}
        class Client:
            calls=[]
            def __init__(client): client.turn=0
            def request(client,purpose,schema,data):
                client.turn+=1
                edits=empty_edits(); edits['texts']['title']='Corrected title'
                if client.turn==1: edits['time_minutes']=0
                else: self.assertIn('time_minutes',data['validation_feedback'][0]['error'])
                return {'base_reference_id':'R1','quest_id':65027,'edits':edits,'unresolved':[],'unsupported':[],'warnings':[]}
        result=compile_project(self.config,project,'hash',65027,'',Client())
        self.assertEqual(len(result['provenance']['validation_repairs']),1)
        self.assertEqual(result['edits']['texts']['title'],'Corrected title')
