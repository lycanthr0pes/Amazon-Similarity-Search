import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  testMatch: ["connected.spec.ts", "connected-parity.spec.ts"],
  workers: 1,
  use: {
    baseURL: "http://127.0.0.1:8766",
    viewport: { width: 1440, height: 1000 },
  },
  webServer: [
    {
      command:
        "uv run --frozen --offline --no-sync python -m tools.browser_search_server --offline-fixture --port 8766 --static-root frontend/dist",
      cwd: "..",
      url: "http://127.0.0.1:8766",
      reuseExistingServer: false,
    },
    {
      command:
        "PYTHONPATH=tests:. uv run --frozen --offline --no-sync python tests/browser_image_free_fixture_server.py",
      cwd: "..",
      url: "http://127.0.0.1:8764",
      reuseExistingServer: false,
    },
  ],
});
