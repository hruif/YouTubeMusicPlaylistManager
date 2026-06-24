// Bundle the Electron main + preload (TypeScript) into electron-dist/ as CJS. esbuild tree-shakes
// and minifies, so youtubei.js (added in Phase 2) ships as one compact file with no node_modules.
// Also compiles the native Swift WKWebView login helper (macOS only).
import { build } from "esbuild";
import { execFileSync } from "node:child_process";

function buildLoginHelper() {
  if (process.platform !== "darwin") {
    console.log("electron: skipping login-helper (macOS only)");
    return;
  }
  // The app ships as a universal binary, so the helper must run on both arches too — otherwise
  // sign-in breaks on whichever Mac the helper wasn't built for. Compile each slice, then lipo them
  // into one fat Mach-O. (swiftc builds a single arch per invocation, hence the per-arch loop.)
  const arches = ["arm64", "x86_64"];
  const slices = [];
  for (const arch of arches) {
    const out = `electron-dist/login-helper-${arch}`;
    execFileSync(
      "swiftc",
      [
        "electron/login-helper/login.swift",
        "-O",
        "-target",
        `${arch}-apple-macos11`,
        "-o",
        out,
        "-framework",
        "WebKit",
        "-framework",
        "AppKit",
        "-framework",
        "Foundation",
      ],
      { stdio: "inherit" },
    );
    slices.push(out);
  }
  execFileSync("lipo", ["-create", "-output", "electron-dist/login-helper", ...slices], {
    stdio: "inherit",
  });
  console.log("electron: built universal login-helper (Swift/WKWebView, arm64 + x86_64)");
}

const watch = process.argv.includes("--watch");

/** @type {import('esbuild').BuildOptions} */
const common = {
  bundle: true,
  platform: "node",
  format: "cjs",
  target: "node20",
  // Electron provides these at runtime; never bundle them.
  external: ["electron"],
  sourcemap: watch ? "inline" : false,
  minify: !watch,
  logLevel: "info",
};

// .cjs extension so Node treats the CJS output as CommonJS despite package.json "type": "module".
const entries = [
  { entryPoints: ["electron/main.ts"], outfile: "electron-dist/main.cjs" },
  { entryPoints: ["electron/preload.ts"], outfile: "electron-dist/preload.cjs" },
];

for (const e of entries) {
  await build({ ...common, ...e });
}
buildLoginHelper();

console.log(`electron: built ${entries.length} bundles${watch ? " (watch not enabled in this run)" : ""}`);
