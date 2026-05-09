import { defineConfig, devices } from "@playwright/test"

const port = Number(process.env.PLM_FRONTEND_E2E_PORT ?? 4173)
const baseURL = process.env.PLM_FRONTEND_E2E_BASE_URL ?? `http://127.0.0.1:${port}`
const command = process.env.PLM_FRONTEND_E2E_USE_DEV_SERVER === "1"
  ? `pnpm exec vite --host 127.0.0.1 --port ${port} --strictPort`
  : `pnpm exec vite preview --host 127.0.0.1 --port ${port} --strictPort`

export default defineConfig({
  testDir: "./tests/e2e",
  timeout: 30_000,
  expect: {
    timeout: 7_500,
  },
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  workers: process.env.CI ? 2 : undefined,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  webServer: {
    command,
    url: baseURL,
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
    env: {
      VITE_API_BASE_URL: "/api",
    },
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
})
