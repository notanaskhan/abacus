// ac-test-author: ayushkbhatia
// W-02-T27 (W-02 §10; WB-01, WB-02, WB-03; T4, TPL-04): the accessibility lock for the built
// Workbench on fixtures. Axe (serious and critical 0) under forced colors and under reduced motion
// on the built Workbench routes and on every T4 and TPL-04 gallery state, and nothing animates once
// reduced motion is set. The keyboard paths (QuestionCard Previous, Skip and Esc; the context
// picker's menuitemcheckbox rows; the Undo toast) are the unit suite
// `packages/ui/src/agent/chat/w02-keyboard.test.tsx`; the Tier C parity report for the 22
// artboards runs in CI (`e2e/parity`), not here.
// Run: `ABACUS_VISUAL=1 pnpm exec playwright test --project=chromium e2e/workbench/a11y.spec.ts`.
import { type Page, expect, test } from "@playwright/test";
import { axeStep } from "../harness/axe";

const E0 = new Date("2026-09-14T09:24:00-05:00");
const ROUTES = ["/workbench", "/workbench/sessions/new"] as const;
const BOARDS: readonly (readonly ["T4" | "TPL-04", string])[] = [
  ...["a", "b", "c", "d", "e", "f"].map((st) => ["T4", st] as const),
  ...["a", "b", "c", "d", "e"].map((st) => ["TPL-04", st] as const),
];

test.use({ viewport: { width: 1440, height: 900 } });

async function route(page: Page, path: string): Promise<void> {
  await page.clock.setFixedTime(E0);
  await page.goto(`${path}?as=hannah-leclerc`);
  await expect(page.locator("main")).toBeVisible();
}

async function board(page: Page, screen: "T4" | "TPL-04", st: string): Promise<void> {
  await page.clock.setFixedTime(E0);
  await page.goto(`/components/screens/${screen}?st=${st}&frame=1&static=1`);
  await expect(page.locator(`[data-artboard='${st}'] [data-template='T4']`)).toBeVisible();
}

async function animating(page: Page): Promise<number> {
  return page.evaluate(
    () =>
      [...document.querySelectorAll<HTMLElement>("*")].filter((el) => {
        const s = getComputedStyle(el);
        return s.animationName !== "none" && s.animationDuration !== "0s";
      }).length,
  );
}

for (const path of ROUTES) {
  test(`test_wb_route_axe_under_forced_colors ${path}`, async ({ page }) => {
    await route(page, path);
    await axeStep(page, `W-02 ${path}`, { forcedColors: true });
  });

  test(`test_wb_route_axe_and_still_under_reduced_motion ${path}`, async ({ page }) => {
    await page.emulateMedia({ reducedMotion: "reduce" });
    await route(page, path);
    await axeStep(page, `W-02 reduced motion ${path}`);
    expect(await animating(page)).toBe(0);
  });
}

for (const [screen, st] of BOARDS) {
  test(`test_${screen.toLowerCase().replace("-", "")}${st}_axe_under_forced_colors_and_reduced_motion`, async ({
    page,
  }) => {
    await page.emulateMedia({ reducedMotion: "reduce" });
    await board(page, screen, st);
    await axeStep(page, `W-02 ${screen}${st}`, { include: "[data-artboard]", forcedColors: true });
    expect(await animating(page)).toBe(0);
  });
}
