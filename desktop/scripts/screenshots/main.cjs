// Minimal Electron shell that loads the website's live demo build (docs/demo/, from
// `npm run build:demo`): the real UI with the in-memory demo backend. Served over a local HTTP
// server, since browsers won't run module scripts from file://.
const { app, BrowserWindow } = require("electron");
const http = require("node:http");
const path = require("node:path");
const os = require("node:os");
const fs = require("node:fs");

const root = path.resolve(__dirname, "../../../docs/demo");
const types = { ".html": "text/html", ".js": "text/javascript", ".css": "text/css", ".png": "image/png" };

app.setPath("userData", fs.mkdtempSync(path.join(os.tmpdir(), "ytmpm-shots-")));
app.whenReady().then(() => {
  const server = http
    .createServer((req, res) => {
      const file = path.join(root, decodeURIComponent(new URL(req.url, "http://x").pathname).replace(/\/$/, "/index.html"));
      if (!file.startsWith(root) || !fs.existsSync(file)) return res.writeHead(404).end();
      res.writeHead(200, { "Content-Type": types[path.extname(file)] ?? "application/octet-stream" });
      fs.createReadStream(file).pipe(res);
    })
    .listen(0, "127.0.0.1", () => {
      const win = new BrowserWindow({
        width: Number(process.env.SHOT_W || 1200),
        height: Number(process.env.SHOT_H || 760),
        show: true,
      });
      win.loadURL(`http://127.0.0.1:${server.address().port}/`);
    });
  app.on("window-all-closed", () => {
    server.close();
    app.quit();
  });
});
