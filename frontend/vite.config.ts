import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 3000,
    proxy: {
      "/api/v1/profiles": {
        target: "http://localhost:8001",
        changeOrigin: true,
      },
      "/api/v1/loans": {
        target: "http://localhost:8002",
        changeOrigin: true,
      },
      "/api/v1/risk": {
        target: "http://localhost:8003",
        changeOrigin: true,
      },
      "/api/v1/cashflow": {
        target: "http://localhost:8004",
        changeOrigin: true,
      },
      "/api/v1/early-warning": {
        target: "http://localhost:8005",
        changeOrigin: true,
      },
      "/api/v1/guidance": {
        target: "http://localhost:8006",
        changeOrigin: true,
      },
      "/api/v1/security": {
        target: "http://localhost:8007",
        changeOrigin: true,
      },
    },
  },
});
