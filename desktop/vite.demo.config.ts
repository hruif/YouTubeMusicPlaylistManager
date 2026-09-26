// Builds the website's live demo: the real renderer with the in-memory demo backend
// (src/demo/), output to ../docs/demo/. Run with `npm run build:demo`.
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

export default defineConfig({
  plugins: [react()],
  root: "demo",
  base: "./",
  publicDir: path.resolve(__dirname, "public"),
  build: {
    outDir: path.resolve(__dirname, "../docs/demo"),
    emptyOutDir: true,
  },
});
