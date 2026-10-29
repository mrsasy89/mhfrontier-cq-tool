use crate::editor::{quest::quest_file::QuestFile, questlist::quest_info::QuestInfo};
use serde::{Deserialize, Serialize};

use super::utils::EventResponse;

#[derive(Serialize, Deserialize, Debug, PartialEq)]
struct SaveQuestPayload {
    filepath: String,
    original_filepath: String,
    quest: QuestFile,
}

#[derive(Serialize, Deserialize, Debug, PartialEq)]
struct ExportQuestInfoPayload {
    filepath: String,
    quest_info: QuestInfo,
}

#[tauri::command]
pub fn save_quest_file(event: String, state: tauri::State<crate::ai_bridge::AiProcess>) -> String {
    let event_payload = serde_json::from_str::<SaveQuestPayload>(&event);
    match event_payload {
        Ok(mut payload) => {
            if let Err(error) = crate::ai_bridge::prepare_save(&state, &payload.filepath) {
                return EventResponse::error(error).to_string();
            }
            let same_path = std::fs::canonicalize(&payload.filepath).ok()
                .zip(std::fs::canonicalize(&payload.original_filepath).ok())
                .map(|(target, source)| target == source).unwrap_or(false);
            if !same_path {
                if let Err(error) = std::fs::copy(&payload.original_filepath, &payload.filepath) {
                    return EventResponse::error(error.to_string()).to_string();
                }
            }
            let result = QuestFile::save_to(&payload.filepath, &mut payload.quest);

            EventResponse::from_result(result).to_string()
        }
        Err(error) => EventResponse::payload_error(error.to_string()).to_string(),
    }
}

#[tauri::command]
pub fn read_quest_file(event: String) -> String {
    let result = QuestFile::from_path(&event);
    EventResponse::from_result_data(result).to_string()
}

#[tauri::command]
pub fn export_quest_info(event: String, state: tauri::State<crate::ai_bridge::AiProcess>) -> String {
    let event_payload = serde_json::from_str::<ExportQuestInfoPayload>(&event);

    match event_payload {
        Ok(mut payload) => {
            if let Err(error) = crate::ai_bridge::prepare_save(&state, &payload.filepath) {
                return EventResponse::error(error).to_string();
            }
            let result = payload.quest_info.save_to(&payload.filepath);

            EventResponse::from_result(result).to_string()
        }
        Err(error) => EventResponse::payload_error(error.to_string()).to_string(),
    }
}
