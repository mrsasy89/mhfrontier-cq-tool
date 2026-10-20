use serde::{Deserialize, Serialize};
use std::collections::HashSet;
use std::fs::{self, File, OpenOptions};
use std::io::{Read, Write};
use std::path::{Path, PathBuf};

#[path = "../editor/translation_bin.rs"]
mod binary;
pub use binary::TranslationStrings;

#[derive(Serialize)]
pub struct BatchQuest {
    path: String,
    name: String,
    quest_id: Option<u16>,
    variant: Option<String>,
    source_stamp: Option<String>,
    strings: Option<TranslationStrings>,
    wrappers: Vec<String>,
    error: Option<String>,
}

#[derive(Deserialize)]
pub struct BatchExport {
    path: String,
    source_stamp: String,
    original_strings: TranslationStrings,
    strings: TranslationStrings,
}

#[derive(Serialize)]
pub struct BatchReport {
    path: String,
    output: Option<String>,
    repacked_jpk3: bool,
    error: Option<String>,
}

fn filename(path: &Path) -> Result<(String, u16, String), String> {
    let name = path
        .file_name()
        .and_then(|name| name.to_str())
        .ok_or("Invalid file name")?;
    let stem = path
        .file_stem()
        .and_then(|stem| stem.to_str())
        .ok_or("Invalid file name")?;
    if !path
        .extension()
        .and_then(|extension| extension.to_str())
        .map(|extension| extension.eq_ignore_ascii_case("bin"))
        .unwrap_or(false)
    {
        return Err("Expected a .bin quest file".into());
    }
    let bytes = stem.as_bytes();
    let start = if bytes.len() == 8 && bytes[5] == b'_' {
        6
    } else {
        5
    };
    if bytes.len() != start + 2
        || !bytes[..5].iter().all(u8::is_ascii_digit)
        || ![b'd', b'n'].contains(&bytes[start])
        || ![b'0', b'1', b'2'].contains(&bytes[start + 1])
    {
        return Err("Expected IDd0/d1/d2/n0/n1/n2.bin (optional underscore)".into());
    }
    let id = stem[..5]
        .parse::<u16>()
        .map_err(|_| "Quest ID is outside uint16 range")?;
    Ok((name.into(), id, stem[start..].into()))
}

fn read_source(path: &Path) -> Result<Vec<u8>, String> {
    let file = File::open(path).map_err(|_| "Unable to open source quest")?;
    let mut data = Vec::new();
    file.take(binary::MAX_FILE as u64 + 1)
        .read_to_end(&mut data)
        .map_err(|_| "Unable to read source quest")?;
    if data.len() > binary::MAX_FILE {
        return Err("Quest exceeds 32 MiB limit".into());
    }
    Ok(data)
}

fn inspect_one(path: String) -> BatchQuest {
    let mut result = BatchQuest {
        name: Path::new(&path)
            .file_name()
            .unwrap_or_default()
            .to_string_lossy()
            .into_owned(),
        path,
        quest_id: None,
        variant: None,
        source_stamp: None,
        strings: None,
        wrappers: Vec::new(),
        error: None,
    };
    let inspect = || -> Result<(u16, String, String, TranslationStrings, Vec<String>), String> {
        let (_, file_id, variant) = filename(Path::new(&result.path))?;
        let source = read_source(Path::new(&result.path))?;
        let source_stamp = binary::stamp(&source);
        let (raw, layers) = binary::unwrap(&source)?;
        let (quest_id, strings) = binary::read_strings(&raw)?;
        if quest_id != file_id {
            return Err("Filename quest ID does not match embedded ID".into());
        }
        Ok((
            quest_id,
            variant,
            source_stamp,
            strings,
            binary::layer_names(&layers),
        ))
    };
    match inspect() {
        Ok((id, variant, stamp, strings, wrappers)) => {
            result.quest_id = Some(id);
            result.variant = Some(variant);
            result.source_stamp = Some(stamp);
            result.strings = Some(strings);
            result.wrappers = wrappers;
        }
        Err(error) => result.error = Some(error),
    }
    result
}

#[cfg_attr(not(feature = "portable-tests"), tauri::command)]
pub async fn inspect_translation_quests(filepaths: Vec<String>) -> Result<Vec<BatchQuest>, String> {
    if filepaths.is_empty() || filepaths.len() > 500 {
        return Err("Select between 1 and 500 quest files".into());
    }
    tokio::task::spawn_blocking(move || filepaths.into_iter().map(inspect_one).collect())
        .await
        .map_err(|_| "Quest inspection worker failed".into())
}

fn export_one(quest: BatchExport, directory: &Path, repack_jpk3: bool) -> BatchReport {
    let mut report = BatchReport {
        path: quest.path.clone(),
        output: None,
        repacked_jpk3: false,
        error: None,
    };
    let export = || -> Result<(PathBuf, bool), String> {
        let (name, file_id, _) = filename(Path::new(&quest.path))?;
        let source = read_source(Path::new(&quest.path))?;
        if binary::stamp(&source) != quest.source_stamp {
            return Err("Source changed since inspection; inspect again".into());
        }
        let (raw, layers) = binary::unwrap(&source)?;
        let (id, current_strings) = binary::read_strings(&raw)?;
        if id != file_id || current_strings != quest.original_strings {
            return Err("Source ID or strings changed since inspection".into());
        }
        let translated = binary::patch_strings(&raw, &quest.strings)?;
        let (encoded, converted) = binary::wrap(&translated, &layers, repack_jpk3)?;
        let destination = directory.join(name);
        let mut file = OpenOptions::new()
            .write(true)
            .create_new(true)
            .open(&destination)
            .map_err(|_| "Output already exists or cannot be created; nothing was overwritten")?;
        if file
            .write_all(&encoded)
            .and_then(|_| file.sync_all())
            .is_err()
        {
            drop(file);
            let _ = fs::remove_file(&destination);
            return Err("Unable to finish output write; original remains unchanged".into());
        }
        drop(file);
        let verification = read_source(&destination).and_then(|data| binary::unwrap(&data));
        match verification {
            Ok((decoded, _)) if decoded == translated => Ok((destination, converted)),
            _ => {
                let _ = fs::remove_file(&destination);
                Err("Output verification failed; incomplete output was removed".into())
            }
        }
    };
    match export() {
        Ok((path, converted)) => {
            report.output = Some(path.to_string_lossy().into_owned());
            report.repacked_jpk3 = converted;
        }
        Err(error) => report.error = Some(error),
    }
    report
}

#[cfg_attr(not(feature = "portable-tests"), tauri::command)]
pub async fn export_translation_quests(
    quests: Vec<BatchExport>,
    output_directory: String,
    repack_jpk3: bool,
) -> Result<Vec<BatchReport>, String> {
    if quests.is_empty() || quests.len() > 500 {
        return Err("Export between 1 and 500 quest files".into());
    }
    let directory = PathBuf::from(output_directory);
    if !directory.is_dir() {
        return Err("Choose an existing output directory".into());
    }
    let mut names = HashSet::new();
    for quest in &quests {
        if let Ok((name, _, _)) = filename(Path::new(&quest.path)) {
            if !names.insert(name.to_ascii_lowercase()) {
                return Err(
                    "Duplicate output filenames; select one source for each variant".into(),
                );
            }
        }
    }
    tokio::task::spawn_blocking(move || {
        quests
            .into_iter()
            .map(|quest| export_one(quest, &directory, repack_jpk3))
            .collect()
    })
    .await
    .map_err(|_| "Quest export worker failed; inspect output report before retrying".into())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn validates_all_six_variant_names() {
        for suffix in ["d0", "d1", "d2", "n0", "n1", "n2"] {
            assert_eq!(
                filename(Path::new(&format!("64551{}.bin", suffix)))
                    .unwrap()
                    .2,
                suffix
            );
            assert!(filename(Path::new(&format!("64551_{}.bin", suffix))).is_ok());
        }
        for name in [
            "64551d3.bin",
            "64551_editor.bin",
            "../quest.bin",
            "99999d0.bin",
            "a.bin",
        ] {
            assert!(filename(Path::new(name)).is_err());
        }
    }
}
