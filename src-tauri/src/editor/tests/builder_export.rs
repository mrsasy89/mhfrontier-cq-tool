//! Independent native read-back of a local Python-builder export; no game files in Git.
use crate::editor::quest::quest_file::QuestFile;

#[test]
#[ignore = "Requires MHFZ_BUILDER_TEST_MANIFEST pointing to a local generated manifest"]
fn builder_export_matches_manifest() {
    let path = std::env::var("MHFZ_BUILDER_TEST_MANIFEST").expect("Local manifest required");
    let report: serde_json::Value = serde_json::from_slice(&std::fs::read(path).unwrap()).unwrap();
    for output in report["outputs"].as_array().unwrap() {
        let quest = QuestFile::from_path(output["path"].as_str().unwrap()).unwrap();
        let expected = &output["summary"];
        assert_eq!(quest.quest_type_flags.main_quest_prop.quest_id as u64, expected["quest_id"].as_u64().unwrap());
        assert_eq!(quest.map_info.map_id as u64, expected["map"].as_u64().unwrap());
        let monsters = expected["monsters"].as_array().unwrap();
        assert_eq!(quest.large_monsters.large_monster_spawns.len(), monsters.len());
        assert_eq!(quest.large_monsters.large_monster_ids.len(), monsters.len());
        for (index, native) in quest.large_monsters.large_monster_spawns.iter().enumerate() {
            let row = &monsters[index];
            assert_eq!(native.monster_id as u64, row["id"].as_u64().unwrap());
            assert_eq!(quest.large_monsters.large_monster_ids[index], native.monster_id as u32);
            assert_eq!(native.spawn_stage as u64, row["stage"].as_u64().unwrap());
            assert_eq!(native.x_position as f64, row["xyz"][0].as_f64().unwrap());
            assert_eq!(native.y_position as f64, row["xyz"][1].as_f64().unwrap());
            assert_eq!(native.z_position as f64, row["xyz"][2].as_f64().unwrap());
        }
        let tables = expected["rewards"].as_array().unwrap();
        assert_eq!(quest.rewards.0.len(), tables.len());
        for (index, table) in quest.rewards.0.iter().enumerate() {
            let row = &tables[index];
            assert_eq!(table.table_header.table_id as u64, row["table"].as_u64().unwrap());
            assert_eq!(table.table_header.unk_0 as u64, row["header_unknown0"].as_u64().unwrap());
            assert_eq!(table.table_header.unk_1 as u64, row["header_unknown1"].as_u64().unwrap());
            let items = row["rows"].as_array().unwrap();
            assert_eq!(table.items.len(), items.len());
            for (offset, item) in table.items.iter().enumerate() {
                assert_eq!(item.item as u64, items[offset]["item"].as_u64().unwrap());
                assert_eq!(item.quantity as u64, items[offset]["amount"].as_u64().unwrap());
                assert_eq!(item.rate as u64, items[offset]["rate"].as_u64().unwrap());
            }
        }
    }
}
