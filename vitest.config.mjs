import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "jsdom",
    setupFiles: ["./tests/client/setup.js"],
    coverage: {
      provider: "v8",
      include: ["src/static/js/script.dev.js"],
      reporter: ["text", "html"],
      reportsDirectory: "htmlcov-client",
      thresholds: {
        branches: 99,
        statements: 99,
        lines: 99,
        functions: 99
      }
    }
  }
});
