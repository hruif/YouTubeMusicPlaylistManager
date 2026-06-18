// Phase 0 auth spike for the Tauri rewrite (see dev-docs/FUTURE_DIRECTIONS.md).
//
// Goal: prove the no-reauth premise — an embedded WKWebView login on macOS that Google does NOT
// block, whose cookies (incl. httpOnly) we can read and use for a real read + write against the
// account, with no manual header copying. Validated: the login works and the WKWebView's
// persistent profile keeps the session across launches, so we can re-capture it silently.
//
// The embedded-WebView sign-in + cookie-capture + HTTP-proxy approach is adapted from
// JustAnotherMusicClient (Apache-2.0); see NOTICE. This spike keeps the credential in memory only
// (no encryption/persistence yet) — persistence comes after the premise is validated.

use std::collections::{HashMap, HashSet};
use std::sync::Mutex;
use std::thread;
use std::time::Duration;

use base64::{engine::general_purpose::STANDARD, Engine as _};
use serde::{Deserialize, Serialize};
use tauri::{Manager, WebviewUrl, WebviewWindow, WebviewWindowBuilder};

const YOUTUBE_LOGIN_WINDOW: &str = "youtube-music-login";
const YOUTUBE_LOGIN_URL: &str =
    "https://accounts.google.com/ServiceLogin?service=youtube&continue=https%3A%2F%2Fmusic.youtube.com%2F";
// A Safari user-agent so Google's sign-in treats the macOS WKWebView like real Safari (the crux of
// why an embedded login is accepted here — see the Tauri-vs-Qt decision in FUTURE_DIRECTIONS.md).
const SAFARI_USER_AGENT: &str =
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.5 Safari/605.1.15";

/// The captured `Cookie:` header for the signed-in YouTube Music session (in-memory only).
#[derive(Default)]
struct SessionState(Mutex<Option<String>>);

/// Shared pooled HTTP client — connection reuse makes batched fetches faster and avoids the
/// transient "error sending request" failures from building a fresh client per request.
struct HttpClient(reqwest::Client);

#[derive(Serialize)]
struct SignInResult {
    cookie: String,
    cookie_names: Vec<String>,
}

fn cookie_domain_is_youtube(domain: Option<&str>) -> bool {
    domain
        .map(|d| d.trim_start_matches('.').ends_with("youtube.com"))
        .unwrap_or(false)
}

/// If the signed-in YouTube Music session is present in the window's cookie store, return the
/// `Cookie:` header plus the captured cookie names (diagnostic).
fn captured_session(window: &WebviewWindow) -> Result<Option<SignInResult>, String> {
    let cookies = window.cookies().map_err(|e| e.to_string())?;
    let yt_cookies: Vec<_> = cookies
        .into_iter()
        .filter(|c| cookie_domain_is_youtube(c.domain()))
        .collect();
    let names: HashSet<&str> = yt_cookies.iter().map(|c| c.name()).collect();
    let has_auth_cookie = ["SAPISID", "__Secure-1PAPISID", "__Secure-3PAPISID"]
        .iter()
        .any(|n| names.contains(n));
    let on_music_page = window
        .url()
        .map(|u| u.host_str() == Some("music.youtube.com"))
        .unwrap_or(false);

    if has_auth_cookie && on_music_page {
        let cookie = yt_cookies
            .iter()
            .map(|c| format!("{}={}", c.name(), c.value()))
            .collect::<Vec<_>>()
            .join("; ");
        let mut cookie_names: Vec<String> = yt_cookies.iter().map(|c| c.name().to_string()).collect();
        cookie_names.sort();
        Ok(Some(SignInResult { cookie, cookie_names }))
    } else {
        Ok(None)
    }
}

fn open_login_window(app: &tauri::AppHandle, visible: bool) -> Result<WebviewWindow, String> {
    if let Some(existing) = app.get_webview_window(YOUTUBE_LOGIN_WINDOW) {
        let _ = existing.close();
    }
    let login_url = url::Url::parse(YOUTUBE_LOGIN_URL).map_err(|e| e.to_string())?;
    WebviewWindowBuilder::new(app, YOUTUBE_LOGIN_WINDOW, WebviewUrl::External(login_url))
        .title("Sign in to YouTube Music")
        .inner_size(520.0, 760.0)
        .visible(visible)
        .user_agent(SAFARI_USER_AGENT)
        .build()
        .map_err(|e| e.to_string())
}

/// Interactive sign-in: open the visible login window and wait (up to ~5 min) for the session.
#[tauri::command]
async fn sign_in_youtube_music(app: tauri::AppHandle) -> Result<SignInResult, String> {
    open_login_window(&app, true)?;

    for _ in 1..=300u32 {
        let window = match app.get_webview_window(YOUTUBE_LOGIN_WINDOW) {
            Some(w) => w,
            None => return Err("Sign-in was cancelled.".to_string()),
        };
        if let Some(result) = captured_session(&window)? {
            *app.state::<SessionState>().0.lock().unwrap() = Some(result.cookie.clone());
            let _ = window.close();
            return Ok(result);
        }
        thread::sleep(Duration::from_secs(1));
    }

    if let Some(window) = app.get_webview_window(YOUTUBE_LOGIN_WINDOW) {
        let _ = window.close();
    }
    Err("Sign-in timed out.".to_string())
}

/// Silent sign-in for startup: open a HIDDEN login window and, if the persisted session redirects
/// straight to music.youtube.com, capture it without ever showing UI. Returns null if not signed
/// in (e.g. first run / signed out), in which case the user must use the interactive flow.
#[tauri::command]
async fn try_silent_sign_in(app: tauri::AppHandle) -> Result<Option<SignInResult>, String> {
    open_login_window(&app, false)?;

    // Give the persisted session a few seconds to load + redirect.
    for _ in 1..=15u32 {
        if let Some(window) = app.get_webview_window(YOUTUBE_LOGIN_WINDOW) {
            if let Some(result) = captured_session(&window)? {
                *app.state::<SessionState>().0.lock().unwrap() = Some(result.cookie.clone());
                let _ = window.close();
                return Ok(Some(result));
            }
        }
        thread::sleep(Duration::from_secs(1));
    }

    if let Some(window) = app.get_webview_window(YOUTUBE_LOGIN_WINDOW) {
        let _ = window.close();
    }
    Ok(None)
}

#[tauri::command]
fn session_status(state: tauri::State<SessionState>) -> bool {
    state.0.lock().unwrap().is_some()
}

#[tauri::command]
fn sign_out_youtube_music(app: tauri::AppHandle, state: tauri::State<SessionState>) {
    *state.0.lock().unwrap() = None;
    if let Some(window) = app.get_webview_window(YOUTUBE_LOGIN_WINDOW) {
        let _ = window.clear_all_browsing_data();
        let _ = window.close();
    }
}

#[derive(Deserialize)]
struct ProxyHttpRequestInput {
    method: String,
    url: String,
    headers: HashMap<String, String>,
    #[serde(default)]
    body_base64: Option<String>,
}

#[derive(Serialize)]
struct ProxyHttpResponse {
    status: u16,
    headers: HashMap<String, String>,
    body_base64: String,
}

/// Faithful HTTP proxy so youtubei.js's fetch can reach YouTube with the session cookies attached
/// (the app's own origin can't send them cross-site). reqwest handles (de)compression, so we strip
/// `accept-encoding` on the way in and `content-encoding`/`content-length` on the way out.
///
/// Crucially, we attach the `Cookie` header from the stored session ourselves: youtubei.js sets it
/// on a WebKit `Headers` object, but WKWebView strips `Cookie` as a forbidden header, so it never
/// reaches us. youtubei.js's `Authorization: SAPISIDHASH` survives; we supply the matching cookie.
#[tauri::command]
async fn proxy_http_request(
    input: ProxyHttpRequestInput,
    state: tauri::State<'_, SessionState>,
    http: tauri::State<'_, HttpClient>,
) -> Result<ProxyHttpResponse, String> {
    let stored_cookie = state.0.lock().unwrap().clone();
    let client = http.0.clone();

    let host = url::Url::parse(&input.url)
        .ok()
        .and_then(|u| u.host_str().map(|h| h.to_string()));
    let is_google_host = host
        .as_deref()
        .map(|h| h.ends_with("youtube.com") || h.ends_with("google.com") || h.ends_with("ytimg.com"))
        .unwrap_or(false);
    let inject_cookie = is_google_host && stored_cookie.is_some();

    let method = reqwest::Method::from_bytes(input.method.as_bytes()).map_err(|e| e.to_string())?;
    let body_bytes: Option<Vec<u8>> = match input.body_base64 {
        Some(b64) => Some(STANDARD.decode(b64).map_err(|e| e.to_string())?),
        None => None,
    };

    // Pooled client + a couple of retries smooths over transient send failures under load.
    let mut response = None;
    let mut last_err = String::from("request failed");
    for attempt in 0..3u32 {
        let mut request = client.request(method.clone(), &input.url);
        for (key, value) in &input.headers {
            if key.eq_ignore_ascii_case("accept-encoding") {
                continue;
            }
            // Drop any (likely stripped/partial) Cookie when we're supplying our own.
            if inject_cookie && key.eq_ignore_ascii_case("cookie") {
                continue;
            }
            request = request.header(key, value);
        }
        if inject_cookie {
            request = request.header("Cookie", stored_cookie.as_deref().unwrap());
        }
        if let Some(bytes) = &body_bytes {
            request = request.body(bytes.clone());
        }
        match request.send().await {
            Ok(r) => {
                response = Some(r);
                break;
            }
            Err(e) => {
                last_err = e.to_string();
                if attempt < 2 {
                    thread::sleep(Duration::from_millis(300));
                }
            }
        }
    }
    let response = response.ok_or(last_err)?;
    let status = response.status().as_u16();
    let mut headers = HashMap::new();
    for (key, value) in response.headers().iter() {
        let lower = key.as_str().to_ascii_lowercase();
        if lower == "content-encoding" || lower == "content-length" {
            continue;
        }
        if let Ok(s) = value.to_str() {
            // A response can carry several Set-Cookie headers; join them so none are lost.
            if lower == "set-cookie" {
                headers
                    .entry("set-cookie".to_string())
                    .and_modify(|v: &mut String| {
                        v.push('\n');
                        v.push_str(s);
                    })
                    .or_insert_with(|| s.to_string());
            } else {
                headers.insert(key.as_str().to_string(), s.to_string());
            }
        }
    }
    let body = response.bytes().await.map_err(|e| e.to_string())?;

    Ok(ProxyHttpResponse {
        status,
        headers,
        body_base64: STANDARD.encode(&body),
    })
}

// --- Local library cache (text JSON in the app data dir) ---------------------------------------
// The library is all text, so caching it lets the app load instantly and fetch only on an explicit
// update (mirrors the Python app's saved_playlists.json). The frontend owns the JSON shape.

fn cache_path(app: &tauri::AppHandle) -> Result<std::path::PathBuf, String> {
    let dir = app.path().app_data_dir().map_err(|e| e.to_string())?;
    std::fs::create_dir_all(&dir).map_err(|e| e.to_string())?;
    Ok(dir.join("library_cache.json"))
}

#[tauri::command]
fn read_cache(app: tauri::AppHandle) -> Result<Option<String>, String> {
    let path = cache_path(&app)?;
    match std::fs::read_to_string(&path) {
        Ok(contents) => Ok(Some(contents)),
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => Ok(None),
        Err(e) => Err(e.to_string()),
    }
}

#[tauri::command]
fn write_cache(app: tauri::AppHandle, contents: String) -> Result<(), String> {
    let path = cache_path(&app)?;
    std::fs::write(&path, contents).map_err(|e| e.to_string())
}

/// Show a native Save dialog and write `contents` to the chosen path. Returns false if cancelled.
#[tauri::command]
fn export_text_file(app: tauri::AppHandle, default_name: String, contents: String) -> Result<bool, String> {
    use tauri_plugin_dialog::DialogExt;
    match app.dialog().file().set_file_name(&default_name).blocking_save_file() {
        Some(path) => {
            let pb = path.into_path().map_err(|e| e.to_string())?;
            std::fs::write(pb, contents).map_err(|e| e.to_string())?;
            Ok(true)
        }
        None => Ok(false),
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let http_client = reqwest::Client::builder()
        .user_agent(SAFARI_USER_AGENT)
        .build()
        .expect("failed to build HTTP client");

    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_dialog::init())
        .manage(SessionState::default())
        .manage(HttpClient(http_client))
        .invoke_handler(tauri::generate_handler![
            sign_in_youtube_music,
            try_silent_sign_in,
            sign_out_youtube_music,
            session_status,
            proxy_http_request,
            read_cache,
            write_cache,
            export_text_file
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
