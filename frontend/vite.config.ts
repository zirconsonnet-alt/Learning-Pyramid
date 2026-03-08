import path from "node:path"
import { defineConfig } from "vite"
import react from "@vitejs/plugin-react"

const backendHost = process.env.PLM_BACKEND_HOST ?? "127.0.0.1"
const backendPort = process.env.PLM_BACKEND_PORT ?? "8001"

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    fs: {
      allow: [path.resolve(__dirname, "..")],
    },
    proxy: {
      "/api": {
        target: `http://${backendHost}:${backendPort}`,
        changeOrigin: true,
      },
    },
  },
})
