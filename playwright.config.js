import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/browser",
  fullyParallel: false,
  workers: 1,
  reporter: "line",
  use: {
    baseURL: "http://127.0.0.1:8769",
    trace: "retain-on-failure"
  },
  webServer: {
    command: "uv run --locked uvicorn main:app --host 127.0.0.1 --port 8769",
    url: "http://127.0.0.1:8769/health",
    reuseExistingServer: !process.env.CI,
    timeout: 30_000,
    env: {
      BACKYARD_BRIDGE_BOT_ACTION_DELAY: "0",
      BACKYARD_BRIDGE_RECONNECT_GRACE_SECONDS: "5",
      BACKYARD_BRIDGE_DEV_ASSETS: "1"
    }
  }
});
