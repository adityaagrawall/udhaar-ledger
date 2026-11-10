import { defineConfig } from "@playwright/test";

const port = process.env.A11Y_PORT || "3001";
const baseURL = process.env.A11Y_BASE_URL || `http://localhost:${port}`;

export default defineConfig({
  testDir: "./e2e",
  timeout: 90_000,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL,
    launchOptions: process.env.A11Y_CHROMIUM ? { executablePath: process.env.A11Y_CHROMIUM } : {},
  },
  // In CI the production build is started for us. Locally, run `npm run build && npm start -- -p 3001` first,
  // or set A11Y_BASE_URL to an already running copy.
  webServer: process.env.CI
    ? { command: `npm run start -- -p ${port}`, url: baseURL, reuseExistingServer: false, timeout: 120_000 }
    : undefined,
});
