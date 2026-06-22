import React from "react";
import ReactDOM from "react-dom/client";
import { showWindow, setBackgroundColor } from "./lib/native";
import App from "./App";

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);

// Match the native window + webview background to the app's --app-bg (per color scheme) so a live
// resize doesn't expose a mismatched strip at the trailing edge.
const darkMq = window.matchMedia("(prefers-color-scheme: dark)");
const applyBackground = () =>
  void setBackgroundColor(darkMq.matches ? [30, 30, 33] : [243, 243, 245]);
applyBackground();
darkMq.addEventListener("change", applyBackground);

// The window starts hidden (Tauri config / Electron show:false) so the webview can paint the styled
// shell before it's shown — no blank/white flash on launch. Reveal it once a frame has painted.
requestAnimationFrame(() =>
  requestAnimationFrame(() => {
    void showWindow();
  }),
);
