import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "path";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd());
  const port = parseInt(env.VITE_PORT ?? "3000", 10);
  const apiUrl = env.VITE_API_URL ?? "http://localhost:5005";

  return {
    plugins: [react(), tailwindcss()],
    resolve: {
      alias: {
        "@": path.resolve(__dirname, "./src"),
      },
    },
    server: {
      port,
      host: "127.0.0.1",
      proxy: {
        "/api": {
          target: apiUrl,
          changeOrigin: true,
        },
        "/static": {
          target: apiUrl,
          changeOrigin: true,
        },
      },
    },
  };
});
