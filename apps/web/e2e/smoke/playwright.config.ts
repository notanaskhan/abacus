import { defineConfig, devices } from "@playwright/test";

// The deploy smoke (Q-01-T32): run by deploy-staging.yml (`--project=deploy-smoke`) after every
// staging batch deploy and by deploy-production.yml (`--project=canary-smoke`) against the
// production canary after a promotion. A red run fails the deploy. Never part of `make e2e`: the
// main config ignores this directory. The whole run fits in 5 minutes (`globalTimeout`).
//
// SMOKE_BASE_URL is the environment's firm host. The signed-in steps (`@signed-in`) run only with
// SMOKE_SIGN_IN=on, once the hosted WorkOS sign-in for the smoke user is registered (sign-in.ts;
// it reads the code from the sink mailbox, F-04-T22). Nothing here holds a credential.
declare const process: { env: Record<string, string | undefined> };

const signedIn = process.env.SMOKE_SIGN_IN === "on";

export default defineConfig({
  testDir: ".",
  testMatch: "deploy-smoke.spec.ts",
  globalTimeout: 300_000,
  timeout: 120_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1,
  retries: 0,
  forbidOnly: true,
  reporter: [
    ["list"],
    ...(process.env.CI === undefined
      ? []
      : ([["html", { open: "never", outputFolder: "../../playwright-report" }]] as const)),
  ],
  ...(signedIn ? {} : { grepInvert: /@signed-in/ }),
  use: {
    ...devices["Desktop Chrome"],
    ...(process.env.SMOKE_BASE_URL === undefined ? {} : { baseURL: process.env.SMOKE_BASE_URL }),
    trace: "retain-on-failure",
    locale: "en-US",
    timezoneId: "America/Chicago",
    reducedMotion: "reduce",
  },
  projects: [
    { name: "deploy-smoke", metadata: { environment: "staging" } },
    { name: "canary-smoke", metadata: { environment: "production" } },
  ],
});
