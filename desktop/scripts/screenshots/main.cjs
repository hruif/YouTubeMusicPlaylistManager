// Minimal Electron shell that loads the built renderer (dist/) with the demo bridge.
const { app, BrowserWindow } = require("electron");
const path = require("node:path");
const os = require("node:os");
const fs = require("node:fs");

app.setPath("userData", fs.mkdtempSync(path.join(os.tmpdir(), "ytmpm-shots-")));
app.whenReady().then(() => {
  const win = new BrowserWindow({
    width: Number(process.env.SHOT_W || 1200),
    height: Number(process.env.SHOT_H || 760),
    show: true,
    webPreferences: { preload: path.join(__dirname, "preload.cjs"), contextIsolation: false, sandbox: false },
  });
  win.loadFile(path.resolve(__dirname, "../../dist/index.html"));
});
app.on("window-all-closed", () => app.quit());
