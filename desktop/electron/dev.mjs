// Dev runner: bundle main/preload, start the Vite dev server, wait for it, then launch Electron
// pointed at it. One command, no extra deps (no concurrently/wait-on).
import { spawn, execFileSync } from "node:child_process";
import { build } from "esbuild";

const PORT = 1420;

async function bundle() {
  const common = {
    bundle: true,
    platform: "node",
    format: "cjs",
    target: "node20",
    external: ["electron"],
    sourcemap: "inline",
    logLevel: "warning",
  };
  await build({ ...common, entryPoints: ["electron/main.ts"], outfile: "electron-dist/main.cjs" });
  await build({ ...common, entryPoints: ["electron/preload.ts"], outfile: "electron-dist/preload.cjs" });
  if (process.platform === "darwin") {
    execFileSync("swiftc", [
      "electron/login-helper/login.swift", "-O", "-o", "electron-dist/login-helper",
      "-framework", "WebKit", "-framework", "AppKit", "-framework", "Foundation",
    ], { stdio: "inherit" });
  }
}

async function waitForServer(port) {
  // Use fetch on `localhost` so it works whether Vite bound to IPv4 or IPv6 (it often listens on
  // [::1] only, which a hardcoded 127.0.0.1 socket would never reach).
  for (;;) {
    try {
      await fetch(`http://localhost:${port}/`);
      return;
    } catch {
      await new Promise((r) => setTimeout(r, 200));
    }
  }
}

await bundle();

const vite = spawn("npx", ["vite", "--port", String(PORT), "--strictPort"], {
  stdio: "inherit",
  shell: false,
});

await waitForServer(PORT);
console.log("vite up — launching electron");

const electronBin = (await import("electron")).default;
const electron = spawn(electronBin, ["."], { stdio: "inherit", shell: false });

const shutdown = () => {
  vite.kill();
  electron.kill();
  process.exit(0);
};
electron.on("close", shutdown);
process.on("SIGINT", shutdown);
process.on("SIGTERM", shutdown);
