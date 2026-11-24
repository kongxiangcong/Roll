import { defineConfig } from "@playwright/test";
const port = Number(process.env.ROLL_E2E_PORT || 18091);
export default defineConfig({
  testDir: "./tests/e2e",
  workers: 1,
  timeout: 180000,
  use: {
    baseURL: "http://127.0.0.1:" + port,
    headless: true,
    launchOptions: {
      executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH,
    },
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
  },
  webServer: {
    command: "npm run build && node tests/e2e/server.mjs",
    url: "http://127.0.0.1:" + port + "/api/session",
    timeout: 120000,
    reuseExistingServer: false,
  },
});
