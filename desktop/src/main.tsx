import React from "react";
import ReactDOM from "react-dom/client";
import { showWindow } from "./lib/native";
import { applyTheme, loadUi, watchSystemTheme } from "./lib/settings";
import App from "./App";

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);

// Apply the saved theme before the first paint, and follow OS appearance changes while on "System".
applyTheme(loadUi().theme);
watchSystemTheme(() => loadUi().theme);

// The window starts hidden (Tauri config / Electron show:false) so the webview can paint the styled
// shell before it's shown — no blank/white flash on launch. Reveal it once a frame has painted.
requestAnimationFrame(() =>
  requestAnimationFrame(() => {
    void showWindow();
  }),
);
