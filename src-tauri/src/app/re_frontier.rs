use super::utils::EventResponse;

#[tauri::command]
pub fn re_frontier(event: String) -> String {
    let _ = event;
    EventResponse::error(String::from("Use AI Quest Builder > Index/decode or unpack: ReFrontier must run on an isolated workspace copy, never the opened quest file.")).to_string()
}
