import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],

  // Relative asset paths so Electron can load the built renderer over file://.
  base: "./",

  // The Electron dev runner (electron/dev.mjs) starts Vite on this fixed port and waits for it.
  server: {
    port: 1420,
    strictPort: true,
  },
});
