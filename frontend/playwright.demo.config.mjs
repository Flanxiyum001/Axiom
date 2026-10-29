import { defineConfig } from "@playwright/test";

// In-memory backend state and no live credentials. Keep this separate from the
// ordinary offline smoke configuration so neither suite changes its defaults.
const python = process.env.AXIOM_TEST_PYTHON || "python";
const safeEnv = {
  PYTHON_DOTENV_DISABLED: "1",
  AXIOM_DEMO_MODE: "1",
  AXIOM_REASONING_PROVIDER: "echo",
  AXIOM_EXECUTOR_BACKEND: "local",
  AXIOM_DB_PATH: ":memory:",
  AXIOM_CORS_ORIGINS: "http://127.0.0.1:3101",
  NEBIUS_API_KEY: "",
  NEBIUS_S3_ACCESS_KEY_ID: "",
  NEBIUS_S3_SECRET_ACCESS_KEY: "",
};

export default defineConfig({
  testDir: "./demo-e2e",
  workers: 1,
  retries: 0,
  timeout: 30_000,
  expect: { timeout: 10_000 },
  reporter: "list",
  use: {
    baseURL: "http://127.0.0.1:3101",
    browserName: "chromium",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  webServer: [
    {
      command: `"${python}" -m uvicorn backend.main:app --host 127.0.0.1 --port 8101 --workers 1`,
      cwd: "..",
      url: "http://127.0.0.1:8101/health",
      env: safeEnv,
      timeout: 30_000,
      reuseExistingServer: false,
    },
    {
      command: "npm run dev -- --hostname 127.0.0.1 --port 3101",
      url: "http://127.0.0.1:3101",
      env: {
        NEXT_PUBLIC_AXIOM_API_URL: "http://127.0.0.1:8101",
        NEXT_PUBLIC_AXIOM_DEMO_MODE: "1",
        NEXT_TELEMETRY_DISABLED: "1",
      },
      timeout: 45_000,
      reuseExistingServer: false,
    },
  ],
});
