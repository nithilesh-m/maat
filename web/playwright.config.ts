import { defineConfig } from "@playwright/test";

const API = "http://127.0.0.1:8090";
const WEB = "http://127.0.0.1:3100";

export default defineConfig({
  testDir: "e2e",
  timeout: 60_000,
  expect: { timeout: 10_000 },
  retries: process.env.CI ? 1 : 0,
  workers: 1, // the tests mutate one seeded backend (reviews, waivers)
  use: { baseURL: WEB, trace: "retain-on-failure", screenshot: "only-on-failure" },
  webServer: [
    {
      command:
        "cd .. && rm -rf runs-e2e && uv run python scripts/seed_demo_runs.py --runs-dir runs-e2e --users runs-e2e/users.toml && " +
        `MAAT_API_RUNS_DIR=runs-e2e MAAT_API_USERS_FILE=runs-e2e/users.toml MAAT_API_ALLOW_ORIGINS=${WEB} uv run maat serve --port 8090`,
      url: `${API}/api/v1/health`,
      reuseExistingServer: !process.env.CI,
      timeout: 180_000,
    },
    {
      command: `NEXT_PUBLIC_MAAT_API=${API} npx next dev -p 3100`,
      url: `${WEB}/login`,
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
  ],
});
