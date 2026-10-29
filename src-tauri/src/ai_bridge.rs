//! Pipes the shared Python wizard to the UI. No shell command interpolation.
use std::io::{BufRead, BufReader, Write};
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::sync::{Arc, atomic::{AtomicBool, Ordering}};
use tauri::{State, Window};

#[derive(Default)]
pub struct AiProcess(pub Mutex<Option<Child>>, pub Mutex<Option<(PathBuf, String)>>, pub Arc<AtomicBool>);

#[tauri::command]
pub fn ai_default_directory() -> String {
    let mut candidates = Vec::new();
    if let Ok(value) = std::env::var("MHFZ_BUILDER_PROJECT") { candidates.push(PathBuf::from(value)); }
    if let Ok(executable) = std::env::current_exe() {
        if let Some(parent) = executable.parent() { candidates.extend(parent.ancestors().map(PathBuf::from)); }
    }
    if let Ok(current) = std::env::current_dir() { candidates.extend(current.ancestors().map(PathBuf::from)); }
    candidates.into_iter().find(|path| path.join("quest_builder.py").is_file())
        .map(|path| path.to_string_lossy().into_owned()).unwrap_or_default()
}

fn detect_python() -> Result<String, String> {
    for program in ["py", "python", "python3"] {
        let mut command = Command::new(program);
        command.args(["-c", "import sys;sys.exit(sys.version_info < (3,11))"])
            .stdin(Stdio::null()).stdout(Stdio::null()).stderr(Stdio::null());
        #[cfg(target_os = "windows")]
        { use std::os::windows::process::CommandExt; command.creation_flags(0x08000000); }
        if command.status().map(|status| status.success()).unwrap_or(false) { return Ok(program.into()); }
    }
    Err("Python 3.11+ was not found. Install it, then reopen the builder.".into())
}

#[tauri::command]
pub fn ai_start(window: Window, state: State<AiProcess>) -> Result<(), String> {
    let detected = ai_default_directory();
    if detected.is_empty() { return Err("Builder files were not found. Start GUI.cmd from the builder project folder.".into()); }
    let root = PathBuf::from(detected).canonicalize().map_err(|e| e.to_string())?;
    let python = detect_python()?;
    let script = root.join("quest_builder.py");
    if !script.is_file() { return Err("Choose the AI Quest Builder project directory containing quest_builder.py".into()); }
    let mut slot = state.0.lock().map_err(|e| e.to_string())?;
    if let Some(child) = slot.as_mut() {
        if child.try_wait().map_err(|e| e.to_string())?.is_none() { return Err("A wizard session is already running. Stop it before starting another.".into()); }
    }
    *state.1.lock().map_err(|e| e.to_string())? = Some((root.clone(), python.clone()));
    let mut command = Command::new(python);
    if state.2.load(Ordering::SeqCst) { command.env("MHFZ_EDITOR_CODEX_READY", "1"); }
    command.arg("-u").arg(script).arg("--config").arg(root.join("quest-builder.local.json"))
        .arg("gui-session").current_dir(root).env("PYTHONIOENCODING", "utf-8")
        .stdin(Stdio::piped()).stdout(Stdio::piped()).stderr(Stdio::piped());
    #[cfg(target_os = "windows")]
    { use std::os::windows::process::CommandExt; command.creation_flags(0x08000000); }
    let mut child = command.spawn().map_err(|e| e.to_string())?;
    let stdout = child.stdout.take().ok_or("Missing wizard output")?;
    let stderr = child.stderr.take().ok_or("Missing wizard error stream")?;
    let output_window = window.clone();
    let account_ready = Arc::clone(&state.2);
    std::thread::spawn(move || {
        for line in BufReader::new(stdout).lines() {
            match line {
                Ok(value) => {
                    if let Ok(message) = serde_json::from_str::<serde_json::Value>(&value) {
                        if message.get("kind").and_then(|v| v.as_str()) == Some("codex-ready") {
                            account_ready.store(true, Ordering::SeqCst);
                        }
                    }
                    let is_message = serde_json::from_str::<serde_json::Value>(&value).ok()
                        .and_then(|message| message.get("kind").cloned()).is_some();
                    let message = if is_message { value } else { serde_json::json!({"kind":"output", "text":value}).to_string() };
                    let _ = output_window.emit("ai-message", message);
                },
                Err(_) => break
            }
        }
        let _ = output_window.emit("ai-ended", ());
    });
    std::thread::spawn(move || {
        for line in BufReader::new(stderr).lines().map_while(Result::ok) {
            let _ = window.emit("ai-message", serde_json::json!({"kind":"output", "text":line}).to_string());
        }
    });
    *slot = Some(child);
    Ok(())
}

#[tauri::command]
pub fn ai_answer(state: State<AiProcess>, answer: String) -> Result<(), String> {
    let mut slot = state.0.lock().map_err(|e| e.to_string())?;
    let input = slot.as_mut().and_then(|child| child.stdin.as_mut()).ok_or("No running wizard")?;
    let line = serde_json::json!({"answer": answer}).to_string();
    writeln!(input, "{}", line).and_then(|_| input.flush()).map_err(|e| e.to_string())
}

pub fn stop(state: &AiProcess) {
    if let Ok(mut slot) = state.0.lock() {
        if let Some(mut child) = slot.take() {
            #[cfg(target_os = "windows")]
            {
                use std::os::windows::process::CommandExt;
                let _ = Command::new("taskkill.exe").args(["/PID", &child.id().to_string(), "/T", "/F"])
                    .creation_flags(0x08000000).output();
            }
            let _ = child.kill(); let _ = child.wait();
        }
    }
}

#[tauri::command]
pub fn ai_stop(state: State<AiProcess>) { stop(&state); }

pub fn prepare_save(state: &AiProcess, target: &str) -> Result<(), String> {
    let mut settings = state.1.lock().map_err(|e| e.to_string())?;
    if settings.is_none() {
        let detected = ai_default_directory();
        if detected.is_empty() { return Err("Builder configuration not found. Open GUI.cmd from the builder folder.".into()); }
        *settings = Some((PathBuf::from(detected), detect_python()?));
    }
    let (root, python) = settings.as_ref().ok_or("Builder workspace is not configured.")?;
    let mut command = Command::new(python);
    command.args(["-m", "mhfz_builder.gui_safety"]).arg(root.join("quest-builder.local.json")).arg(target)
        .current_dir(root).env("PYTHONIOENCODING", "utf-8");
    #[cfg(target_os = "windows")]
    { use std::os::windows::process::CommandExt; command.creation_flags(0x08000000); }
    let output = command.output().map_err(|e| e.to_string())?;
    if output.status.success() { Ok(()) } else { Err(String::from_utf8_lossy(&output.stderr).trim().to_string()) }
}
