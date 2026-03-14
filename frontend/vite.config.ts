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
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          const normalizedId = id.replace(/\\/g, "/")
          if (!normalizedId.includes("/node_modules/")) return undefined
          if (normalizedId.includes("/node_modules/hls.js/")) return "hls"
          if (normalizedId.includes("/node_modules/katex/")) return "katex"
          if (
            /\/node_modules\/(react|react-dom|scheduler|react-router|react-router-dom|@tanstack|zod|zustand)\//.test(
              normalizedId,
            )
          ) {
            return "framework"
          }
          if (
            /\/node_modules\/(@radix-ui|lucide-react|class-variance-authority|clsx|tailwind-merge|tailwindcss-animate)\//.test(
              normalizedId,
            )
          ) {
            return "ui-kit"
          }
          return "vendor"
        },
      },
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
