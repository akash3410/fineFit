import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    // TypeScript sources are authoritative. List them before .js so any stray
    // emitted compiler output can never shadow the real components.
    extensions: [".tsx", ".ts", ".mts", ".mjs", ".jsx", ".js", ".json"],
  },
  server: {
    proxy: {
      "/api": "http://127.0.0.1:8000",
      "/media": "http://127.0.0.1:8000",
    },
  },
});
