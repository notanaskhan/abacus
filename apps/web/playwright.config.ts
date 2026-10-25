import { defineConfig, devices } from "@playwright/test";

// Node's environment, without pulling Node's types into the SPA's build.
declare const process: { env: Record<string, string | undefined> };
// This worktree's port offset (F-01-T09; `make worktree-env`): 0 in the primary checkout and CI.
const offset = Number(process.env.ABACUS_PORT_OFFSET ?? "0") || 0;
// The visual project (F-05-T16) runs against the gallery alone, with no API and no database:
// `pnpm visual` sets ABACUS_VISUAL=1 and Playwright starts vite on fixtures itself. A busy port is
// handled with ABACUS_VISUAL_PORT.
const visual = process.env.ABACUS_VISUAL === "1";
const visualPort = Number(process.env.ABACUS_VISUAL_PORT ?? String(5173 + offset));
// The journey harness's fixture project (F-04-T21) needs the same server: ABACUS_FIXTURES=1 starts
// it, or `make dev-fixtures` is already running on the port.
const fixtureServer = visual || process.env.ABACUS_FIXTURES === "1";
const local = `http://localhost:${String(5173 + offset)}`;

// The journey harness's four projects (F-04-T21; F-04.32). One spec runs in each; the persona
// adapter for the project (`metadata.harness`, e2e/harness/adapters.ts) signs the persona in.
// fullstack is `make dev` + `make seed-demo` on the local stack, never a hosted database; staging
// and canary run only where their URL is set (the nightly and release jobs, F-04-T28).
const JOURNEY_FILES = ["**/journeys/**/*.spec.ts", "**/harness/**/*.spec.ts"];
const journeyUse = {
  ...devices["Desktop Chrome"],
  viewport: { width: 1440, height: 900 },
  reducedMotion: "reduce" as const,
  locale: "en-US",
  timezoneId: "America/Chicago",
};
const hosted = (url: string | undefined) => (url === undefined ? {} : { baseURL: url });

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
  reporter: [
    ["list"],
    ["./e2e/visual/parity-reporter.ts"],
    ...(process.env.CI === undefined
      ? []
      : ([["html", { open: "never", outputFolder: "playwright-report" }]] as const)),
  ],
  use: {
    baseURL: local,
    trace: "retain-on-failure",
  },
  projects: [
    {
      name: "chromium",
      testIgnore: ["**/visual/**", "**/parity/**", ...JOURNEY_FILES],
      use: { ...devices["Desktop Chrome"] },
    },
    {
      // Parity Tier A to D, and the gallery screenshot regression (chapter 04 §9.3): the render
      // the handoff's PNGs were cropped for, 1440 x 900 at 2x, light, motion reduced.
      name: "visual",
      testDir: "./e2e/visual",
      snapshotDir: "./.visual",
      snapshotPathTemplate: "{snapshotDir}/{testFileName}/{arg}{ext}",
      use: {
        ...devices["Desktop Chrome"],
        baseURL: `http://localhost:${String(visualPort)}`,
        viewport: { width: 1440, height: 900 },
        deviceScaleFactor: 2,
        colorScheme: "light",
        reducedMotion: "reduce",
        locale: "en-US",
        timezoneId: "America/Chicago",
      },
    },
    {
      // The local screen parity report (F-04-T33): every artboard of each fixture or live screen
      // against its cropped handoff PNG, rendered as the visual project renders; it reads the
      // baselines `pnpm visual:baselines` fetched for parity.spec.ts. `pnpm parity:screens`.
      name: "parity-screens",
      testDir: "./e2e/parity",
      snapshotDir: "./.visual",
      snapshotPathTemplate: "{snapshotDir}/parity.spec.ts/{arg}{ext}",
      use: {
        ...devices["Desktop Chrome"],
        baseURL: `http://localhost:${String(visualPort)}`,
        viewport: { width: 1440, height: 900 },
        deviceScaleFactor: 2,
        colorScheme: "light",
        reducedMotion: "reduce",
        locale: "en-US",
        timezoneId: "America/Chicago",
      },
    },
    {
      name: "fixture",
      testMatch: JOURNEY_FILES,
      metadata: { harness: "fixture" },
      use: { ...journeyUse, baseURL: `http://localhost:${String(visualPort)}` },
    },
    {
      name: "fullstack",
      testMatch: JOURNEY_FILES,
      metadata: { harness: "fullstack" },
      use: { ...journeyUse, baseURL: local },
    },
    {
      name: "staging",
      testMatch: JOURNEY_FILES,
      metadata: { harness: "staging" },
      use: { ...journeyUse, ...hosted(process.env.ABACUS_STAGING_URL) },
    },
    {
      name: "canary",
      testMatch: JOURNEY_FILES,
      metadata: { harness: "canary" },
      use: { ...journeyUse, ...hosted(process.env.ABACUS_CANARY_URL) },
    },
  ],
  ...(fixtureServer
    ? {
        webServer: {
          command: `pnpm exec vite --port ${String(visualPort)} --strictPort`,
          url: `http://localhost:${String(visualPort)}/components`,
          reuseExistingServer: process.env.CI === undefined,
          timeout: 120_000,
          env: { VITE_UI_GALLERY: "1", VITE_FIXTURES: "1" },
        },
      }
    : {}),
});
