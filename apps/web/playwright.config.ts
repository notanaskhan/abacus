import { defineConfig, devices } from "@playwright/test";

// Node's environment, without pulling Node's types into the SPA's build.
declare const process: { env: Record<string, string | undefined> };
// This worktree's port offset (F-01-T09; `make worktree-env`): 0 in the primary checkout and CI.
const offset = Number(process.env.ABACUS_PORT_OFFSET ?? "0") || 0;

// The journey runs against the local stack: `make dev` running and `make seed` done (`make e2e`).
export default defineConfig({
  testDir: "./e2e",
  testMatch: "**/*.spec.ts",
  timeout: 240_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1,
  retries: 0,
  forbidOnly: true,
  reporter: [["list"]],
  use: {
    baseURL: `http://localhost:${String(5173 + offset)}`,
    trace: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
