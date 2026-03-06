import { defineConfig } from "vite";
import react from "@vitejs/plugin-react-swc";

export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0", // required for Docker: listen on all interfaces
    port: 5173,
    // Proxy /api to the backend. When frontend runs on host: 127.0.0.1:8000. When in Docker: backend-api:8000.
    proxy: {
      "/api": {
        target: process.env.VITE_PROXY_TARGET ?? "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
});

