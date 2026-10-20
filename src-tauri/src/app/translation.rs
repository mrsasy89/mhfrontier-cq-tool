//! Optional LibreTranslate transport. Quest data and provider credentials are never logged.
use encoding_rs::SHIFT_JIS;
use reqwest::{redirect::Policy, Client, Url};
use serde_json::{json, Value};
use std::time::Duration;

const MAX_TEXTS: usize = 64;
const MAX_TEXT_BYTES: usize = 8 * 1024;
const MAX_INPUT_BYTES: usize = 32 * 1024;
const MAX_BODY_BYTES: usize = 64 * 1024;
const MAX_RESPONSE_BYTES: usize = 256 * 1024;

fn translation_url(endpoint: &str) -> Result<Url, String> {
    let mut url =
        Url::parse(endpoint.trim()).map_err(|_| "Enter a valid LibreTranslate base URL.")?;
    let local = matches!(url.host_str(), Some("localhost" | "127.0.0.1" | "[::1]"));
    if url.host_str().is_none()
        || !(url.scheme() == "https" || (url.scheme() == "http" && local))
        || !url.username().is_empty()
        || url.password().is_some()
        || url.query().is_some()
        || url.fragment().is_some()
    {
        return Err("Use HTTPS, or HTTP on localhost only. Do not include credentials, queries or fragments in the URL.".into());
    }
    let path = url.path().trim_end_matches('/');
    if !path.ends_with("/translate") {
        url.set_path(&format!("{}/translate", path));
    }
    Ok(url)
}

fn has_invalid_controls(text: &str) -> bool {
    text.chars()
        .any(|c| c.is_control() && !matches!(c, '\n' | '\r' | '\t'))
}

fn request_body(texts: &[String], api_key: Option<&str>) -> Result<Value, String> {
    if texts.is_empty() || texts.len() > MAX_TEXTS {
        return Err("Translate between 1 and 64 text blocks per request.".into());
    }
    if texts
        .iter()
        .any(|s| s.len() > MAX_TEXT_BYTES || has_invalid_controls(s))
        || texts.iter().map(|s| s.len()).sum::<usize>() > MAX_INPUT_BYTES
    {
        return Err("Text contains unsupported control characters or exceeds the translation request limit.".into());
    }
    let mut body = json!({ "q": texts, "source": "ja", "target": "en", "format": "text" });
    if let Some(key) = api_key.filter(|key| !key.trim().is_empty()) {
        if key.len() > 4096 {
            return Err("The API key is too long.".into());
        }
        body["api_key"] = Value::String(key.to_owned());
    }
    let size = serde_json::to_vec(&body)
        .map_err(|_| "Could not prepare the translation request.")?
        .len();
    if size > MAX_BODY_BYTES {
        return Err("The translation request is too large.".into());
    }
    Ok(body)
}

fn translated_texts(body: &[u8], count: usize) -> Result<Vec<String>, String> {
    let json: Value = serde_json::from_slice(body)
        .map_err(|_| "LibreTranslate returned an invalid JSON response.")?;
    let values = match &json["translatedText"] {
        Value::Array(values) if values.len() == count => values
            .iter()
            .map(|value| value.as_str().map(str::to_owned))
            .collect::<Option<Vec<_>>>(),
        Value::String(text) if count == 1 => Some(vec![text.clone()]),
        _ => None,
    }
    .ok_or("LibreTranslate returned an unexpected number or type of translations.")?;
    validate_target_texts(&values)?;
    Ok(values)
}

fn validate_target_texts(texts: &[String]) -> Result<(), String> {
    if texts.is_empty() || texts.len() > MAX_TEXTS {
        return Err("Validate between 1 and 64 text blocks per request.".into());
    }
    if texts.iter().map(|text| text.len()).sum::<usize>() > MAX_INPUT_BYTES {
        return Err("The translation text batch is too large.".into());
    }
    for text in texts {
        if text.len() > MAX_TEXT_BYTES || has_invalid_controls(text) {
            return Err("A translation exceeds the text limit or contains unsupported control characters.".into());
        }
        let (_, _, errors) = SHIFT_JIS.encode(text);
        if errors {
            return Err("A translation contains characters that cannot be saved as Shift-JIS. Review or replace them before applying.".into());
        }
    }
    Ok(())
}

#[cfg_attr(not(feature = "portable-tests"), tauri::command)]
pub fn validate_translation_texts(texts: Vec<String>) -> Result<(), String> {
    validate_target_texts(&texts)?;
    if texts.len() != 8 {
        return Err("Validate all eight quest text fields together.".into());
    }
    let encoded_bytes: usize = texts.iter().map(|text| SHIFT_JIS.encode(text).0.len()).sum();
    if encoded_bytes > 512 {
        return Err("The eight texts exceed the Erupe v9.6.1 ZZ event budget of 512 Shift-JIS bytes. Shorten the text before applying.".into());
    }
    Ok(())
}

#[cfg_attr(not(feature = "portable-tests"), tauri::command)]
pub async fn translate_quest_text(
    endpoint: String,
    texts: Vec<String>,
    api_key: Option<String>,
) -> Result<Vec<String>, String> {
    let url = translation_url(&endpoint)?;
    let body = request_body(&texts, api_key.as_deref())?;
    let client = Client::builder()
        .redirect(Policy::none())
        .connect_timeout(Duration::from_secs(10))
        .timeout(Duration::from_secs(90))
        .build()
        .map_err(|_| "Could not initialize the translation connection.")?;
    let mut response = client
        .post(url)
        .json(&body)
        .send()
        .await
        .map_err(|_| "Cannot reach LibreTranslate. Check its URL, availability and TLS certificate, then retry.")?;
    match response.status().as_u16() {
        200..=299 => {}
        401 | 403 => {
            return Err("LibreTranslate rejected access. Check the optional API key.".into())
        }
        429 => return Err("LibreTranslate rate limit reached. Wait before retrying; no quest text was changed.".into()),
        _ => return Err("LibreTranslate could not complete the request. Check the service configuration and Japanese-to-English model availability.".into()),
    }
    if response
        .content_length()
        .map_or(false, |n| n > MAX_RESPONSE_BYTES as u64)
    {
        return Err("LibreTranslate returned an oversized response.".into());
    }
    let mut bytes = Vec::new();
    while let Some(chunk) = response
        .chunk()
        .await
        .map_err(|_| "The translation response was interrupted. Retry the request.")?
    {
        if bytes.len() + chunk.len() > MAX_RESPONSE_BYTES {
            return Err("LibreTranslate returned an oversized response.".into());
        }
        bytes.extend_from_slice(&chunk);
    }
    let translated = translated_texts(&bytes, texts.len())?;
    if texts
        .iter()
        .zip(&translated)
        .any(|(source, target)| !source.trim().is_empty() && target.trim().is_empty())
    {
        return Err("LibreTranslate returned an empty translation for nonempty text.".into());
    }
    Ok(translated)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn accepts_local_and_https_base_urls() {
        assert_eq!(
            translation_url("http://127.0.0.1:5000/")
                .unwrap()
                .as_str(),
            "http://127.0.0.1:5000/translate"
        );
        assert_eq!(
            translation_url("http://[::1]:5000").unwrap().path(),
            "/translate"
        );
        assert_eq!(
            translation_url("https://example.org/libre/")
                .unwrap()
                .path(),
            "/libre/translate"
        );
        assert_eq!(
            translation_url("https://example.org/translate")
                .unwrap()
                .path(),
            "/translate"
        );
    }

    #[test]
    fn rejects_credentials_and_unsecured_remote_urls() {
        for url in [
            "http://example.org",
            "https://user:secret@example.org",
            "https://example.org?key=x",
            "https://example.org#x",
            "file:///tmp/a",
        ] {
            assert!(translation_url(url).is_err());
        }
    }

    #[test]
    fn key_is_optional_and_requests_are_bounded() {
        let texts = vec!["日本語".to_owned()];
        assert!(request_body(&texts, None).unwrap().get("api_key").is_none());
        assert_eq!(request_body(&texts, Some("key")).unwrap()["api_key"], "key");
        assert!(request_body(&[], None).is_err());
        assert!(request_body(&vec!["a".into(); MAX_TEXTS + 1], None).is_err());
        assert!(request_body(&vec!["a".repeat(MAX_TEXT_BYTES + 1)], None).is_err());
        assert!(request_body(&vec!["a\0b".into()], None).is_err());
    }

    #[test]
    fn validates_provider_response_without_lossy_conversion() {
        assert_eq!(
            translated_texts(br#"{"translatedText":["Hello","World"]}"#, 2).unwrap(),
            vec!["Hello", "World"]
        );
        assert_eq!(
            translated_texts(br#"{"translatedText":"Hello"}"#, 1).unwrap(),
            vec!["Hello"]
        );
        assert!(translated_texts(br#"{"translatedText":"Hello"}"#, 2).is_err());
        assert!(translated_texts(br#"{"translatedText":[123]}"#, 1).is_err());
        assert!(translated_texts(br#"{"translatedText":["bad\u0000text"]}"#, 1).is_err());
        assert!(translated_texts("{\"translatedText\":[\"😀\"]}".as_bytes(), 1).is_err());
        assert!(translated_texts(b"not-json", 1).is_err());
    }

    #[test]
    fn validates_user_edited_preview_without_network() {
        let mut fields = vec![String::new(); 8];
        fields[0] = "Edited English\ntext".into();
        assert!(validate_translation_texts(fields.clone()).is_ok());
        fields[0] = "x".repeat(513);
        assert!(validate_translation_texts(fields).is_err());
        assert!(validate_translation_texts(vec![String::new(); 8]).is_ok());
        assert!(validate_translation_texts(vec!["Bad\0text".into()]).is_err());
        assert!(validate_translation_texts(vec!["Emoji 😀".into()]).is_err());
        assert!(validate_translation_texts(Vec::new()).is_err());
    }
}
