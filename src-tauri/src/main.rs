#![cfg_attr(
    all(not(debug_assertions), target_os = "windows"),
    windows_subsystem = "windows"
)]

pub mod app;
pub mod editor;
mod ai_bridge;

use app::*;
use tauri;
use tauri::Manager;

#[tokio::main]
async fn main() {
    tauri::Builder::default()
        .manage(ai_bridge::AiProcess::default())
        .on_window_event(|event| {
            if let tauri::WindowEvent::Destroyed = event.event() {
                ai_bridge::stop(&event.window().state::<ai_bridge::AiProcess>());
            }
        })
        .invoke_handler(tauri::generate_handler![
            ai_bridge::ai_start,
            ai_bridge::ai_default_directory,
            ai_bridge::ai_answer,
            ai_bridge::ai_stop,
            read_quest_file,
            save_quest_file,
            export_quest_info,
            read_all_questlist,
            read_questinfo,
            re_frontier,
            get_config,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
