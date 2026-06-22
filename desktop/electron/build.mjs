// Bundle the Electron main + preload (TypeScript) into electron-dist/ as CJS. esbuild tree-shakes
// and minifies, so youtubei.js (added in Phase 2) ships as one compact file with no node_modules.
import { build } from "esbuild";

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

console.log(`electron: built ${entries.length} bundles${watch ? " (watch not enabled in this run)" : ""}`);
