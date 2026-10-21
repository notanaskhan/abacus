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
    baseURL: `http://localhost:${String(5173 + offset)}`,
    trace: "retain-on-failure",
  },
  projects: [
    {
      name: "chromium",
      testIgnore: "**/visual/**",
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
  ],
  ...(visual
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
