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
#[tauri::command]
async fn proxy_http_request(input: ProxyHttpRequestInput) -> Result<ProxyHttpResponse, String> {
    let method = reqwest::Method::from_bytes(input.method.as_bytes()).map_err(|e| e.to_string())?;
    let client = reqwest::Client::builder()
        .user_agent(SAFARI_USER_AGENT)
        .build()
        .map_err(|e| e.to_string())?;

    let mut request = client.request(method, &input.url);
    for (key, value) in &input.headers {
        if key.eq_ignore_ascii_case("accept-encoding") {
            continue;
        }
        request = request.header(key, value);
    }
    if let Some(body_base64) = input.body_base64 {
        let bytes = STANDARD.decode(body_base64).map_err(|e| e.to_string())?;
        request = request.body(bytes);
    }

    let response = request.send().await.map_err(|e| e.to_string())?;
    let status = response.status().as_u16();
    let mut headers = HashMap::new();
    for (key, value) in response.headers().iter() {
        let lower = key.as_str().to_ascii_lowercase();
        if lower == "content-encoding" || lower == "content-length" {
            continue;
        }
        if let Ok(s) = value.to_str() {
            headers.insert(key.as_str().to_string(), s.to_string());
        }
    }
    let body = response.bytes().await.map_err(|e| e.to_string())?;

    Ok(ProxyHttpResponse {
        status,
        headers,
        body_base64: STANDARD.encode(&body),
    })
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .manage(SessionState::default())
        .invoke_handler(tauri::generate_handler![
            sign_in_youtube_music,
            try_silent_sign_in,
            sign_out_youtube_music,
            session_status,
            proxy_http_request
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
