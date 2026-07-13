import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Local-only configuration.
// - Dev server binds to loopback and port 5173 (strict).
// - /api is proxied to the local FastAPI backend on 127.0.0.1:8000.
// - No CDN, no remote fonts, no analytics, no telemetry.
export default defineConfig({
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    port: 5173,
    strictPort: true,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: false,
      },
    },
  },
  preview: {
    host: "127.0.0.1",
    port: 5173,
    strictPort: true,
  },
  build: {
    // Inline nothing from remote origins; keep assets relative for file-served demos.
    assetsDir: "assets",
    sourcemap: false,
  },
});
