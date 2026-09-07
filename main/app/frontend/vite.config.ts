import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { resolve } from "node:path";

/**
 * Two run modes, and the proxy is what makes them behave identically:
 *
 *   dev   `npm run dev`  → Vite on :5173, /api proxied to the FastAPI server
 *   prod  `npm run build` → static bundle in dist/, served by FastAPI itself
 *
 * Because the proxy rewrites nothing, every fetch in the app can use a plain
 * relative '/api/...' path. No environment-specific base URL, no CORS in dev,
 * and no code that behaves differently depending on how it was started.
 */
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { "@": resolve(__dirname, "./src") },
  },
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: process.env.VITE_API_TARGET ?? "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: "dist",
    sourcemap: true,
  },
});
