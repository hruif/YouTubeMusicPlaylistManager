import React from "react";
import ReactDOM from "react-dom/client";
import { getCurrentWindow } from "@tauri-apps/api/window";
import { getCurrentWebviewWindow } from "@tauri-apps/api/webviewWindow";
import App from "./App";

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);

// Match the native window + webview background to the app's --app-bg (per color scheme). During a
// live window resize, WKWebView lets the page content trail the window edge for a frame or two,
// briefly exposing this background — if it matches the app it's nearly invisible instead of a white
// strip, which is most of the *perceived* resize lag on macOS. Set before the window is revealed.
const wv = getCurrentWebviewWindow();
const darkMq = window.matchMedia("(prefers-color-scheme: dark)");
const applyBackground = () =>
  void wv.setBackgroundColor(darkMq.matches ? [30, 30, 33] : [243, 243, 245]).catch(() => {});
applyBackground();
darkMq.addEventListener("change", applyBackground);

// The window starts hidden (tauri.conf.json) so the webview can paint the styled shell before it's
// shown — no blank/white flash on launch. Reveal it once a frame has actually painted (double rAF).
// A Rust-side timeout (lib.rs) re-shows it regardless, so this can never strand the window hidden.
requestAnimationFrame(() =>
  requestAnimationFrame(() => {
    void getCurrentWindow().show();
  }),
);
