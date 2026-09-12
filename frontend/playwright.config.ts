import { defineConfig } from "@playwright/test";

const development = process.env.UI_TEST_MODE === "development";
const port = development ? 5175 : 4173;
const baseURL = `http://127.0.0.1:${port}`;

export default defineConfig({
  testDir: "./e2e",
  testIgnore: "connected*.spec.ts",
  fullyParallel: true,
  use: {
    baseURL,
    viewport: { width: 1440, height: 1000 },
  },
  webServer: {
    command: development ? `npm run dev -- --port ${port}` : "npm run preview",
    url: baseURL,
    reuseExistingServer: false,
  },
});
