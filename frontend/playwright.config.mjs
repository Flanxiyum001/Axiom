import { defineConfig } from "@playwright/test";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";

// Unique storage for each invocation; never reuse a developer's DB/artifacts.
const storage = mkdtempSync(path.join(tmpdir(), "axiom-smoke-"));
const python = process.env.AXIOM_TEST_PYTHON || "python";
const safeEnv = {
  PYTHON_DOTENV_DISABLED: "1",
  AXIOM_REASONING_PROVIDER: "echo",
  AXIOM_EXECUTOR_BACKEND: "local",
  AXIOM_DB_PATH: path.join(storage, "smoke.db"),
  AXIOM_ARTIFACT_ROOT: path.join(storage, "artifacts"),
  AXIOM_CORS_ORIGINS: "http://127.0.0.1:3100",
  NEBIUS_API_KEY: "",
  NEBIUS_S3_ACCESS_KEY_ID: "",
  NEBIUS_S3_SECRET_ACCESS_KEY: "",
  PYTHONUTF8: "1",
  PYTHONIOENCODING: "utf-8",
};

export default defineConfig({
  testDir: "./e2e",
  workers: 1,
  retries: 0,
  timeout: 90_000,
  expect: { timeout: 15_000 },
  reporter: "list",
  use: {
    baseURL: "http://127.0.0.1:3100",
    browserName: "chromium",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  webServer: [
    {
      command: `"${python}" -m uvicorn backend.main:app --host 127.0.0.1 --port 8100`,
      cwd: "..",
      url: "http://127.0.0.1:8100/health",
      env: safeEnv,
      timeout: 30_000,
      reuseExistingServer: false,
    },
    {
      command: "npm run dev -- --hostname 127.0.0.1 --port 3100",
      url: "http://127.0.0.1:3100",
      env: { NEXT_PUBLIC_AXIOM_API_URL: "http://127.0.0.1:8100", NEXT_TELEMETRY_DISABLED: "1" },
      timeout: 45_000,
      reuseExistingServer: false,
    },
  ],
});
