import React from "react";
import ReactDOM from "react-dom/client";
import { getCurrentWindow } from "@tauri-apps/api/window";
import App from "./App";

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);

// The window starts hidden (tauri.conf.json) so the webview can paint the styled shell before it's
// shown — no blank/white flash on launch. Reveal it once a frame has actually painted (double rAF).
// A Rust-side timeout (lib.rs) re-shows it regardless, so this can never strand the window hidden.
requestAnimationFrame(() =>
  requestAnimationFrame(() => {
    void getCurrentWindow().show();
  }),
);
