import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath, URL } from "node:url";

// Dev server proxies the real Relay API so the client speaks to live Postgres-backed
// endpoints with no CORS ceremony. Nothing is mocked. The target is configurable
// so the same client works locally (127.0.0.1) and inside Docker Compose (api:8000).
const API_TARGET = process.env.RELAY_API_TARGET ?? "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  server: {
    host: true,
    port: 3000,
    proxy: {
      "/v1": { target: API_TARGET, changeOrigin: true },
      "/health": { target: API_TARGET, changeOrigin: true },
    },
  },
});
