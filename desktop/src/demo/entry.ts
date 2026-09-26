// Entry point of the website's live demo (see vite.demo.config.ts). The bridge must be installed
// before the app's modules load, since lib/native reads window.electronAPI when it's imported.
import { createDemoBackend } from "./bridge";
import { DEMO_UI } from "./data";

(globalThis as unknown as { electronAPI: unknown }).electronAPI = createDemoBackend();
try {
  if (!localStorage.getItem("ytm.ui")) localStorage.setItem("ytm.ui", JSON.stringify(DEMO_UI));
} catch {
  /* storage blocked: the app falls back to defaults */
}
await import("../main");
