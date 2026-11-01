// AUD-11 and AUD-31 in fixture mode (A-03-T19; A-03 §10 DoD): every scenario state at 1440×900,
// DPR 2, from the /components gallery, with axe at zero serious or critical findings in every
// state (the C-20 states included), and a keyboard path from the top of each artboard to its first
// control with a visible focus ring. Tier C parity is reported by e2e/parity/screens.spec.ts from
// the contracts' "## Parity" tables (AUD-11 a–f, AUD-31 f; a, f and AUD-31 f locked); AUD-31's
// composed a2–e2 are Tier D. AUD-11 g is recorded for X-01 and AUD-31 a–e for A-09.
// Run: `ABACUS_VISUAL=1 pnpm exec playwright test --project=chromium e2e/screens/A03-sampling-mapping.spec.ts`.
import AxeBuilder from "@axe-core/playwright";
import { type Page, expect, test } from "@playwright/test";

const SERIOUS = new Set(["serious", "critical"]);
const STATES = {
  "AUD-11": ["a", "b", "c", "d", "e", "f", "picker", "off", "not_allowed", "loading", "error"],
  "AUD-31": ["f", "a2", "b2", "c2", "d2", "e2", "off", "not_allowed", "loading", "error"],
} as const;
// States with a control to reach (the C-20 off, walled, loading and error states have none).
const ACTIONABLE = new Set(["a", "b", "c", "d", "e", "f", "picker", "a2", "c2", "d2", "e2"]);
const TAB_LIMIT = 40;

test.use({
  viewport: { width: 1440, height: 900 },
  deviceScaleFactor: 2,
  reducedMotion: "reduce",
});

async function seriousFindings(page: Page, st: string): Promise<string[]> {
  const { violations } = await new AxeBuilder({ page })
    .include(`[data-artboard='${st}']`)
    .analyze();
  return violations
    .filter((v) => SERIOUS.has(v.impact ?? ""))
    .map((v) => `${v.id}: ${v.help} — ${v.nodes[0]?.target.join(" ") ?? ""}`);
}

async function reachesAControl(page: Page, st: string): Promise<boolean> {
  const board = page.locator(`[data-artboard='${st}']`);
  await board.evaluate((el: HTMLElement) => {
    el.tabIndex = -1;
    el.focus();
  });
  for (let i = 0; i < TAB_LIMIT; i += 1) {
    await page.keyboard.press("Tab");
    const reached = await board.evaluate((el) => {
      const modal = document.querySelector("[role='dialog'], [role='alertdialog']");
      const root = modal ?? el;
      const active = document.activeElement;
      if (active === null || !root.contains(active)) return false;
      const style = getComputedStyle(active);
      const ring = style.outlineStyle !== "none" || style.boxShadow !== "none";
      const control = "a[href], button, [role='row'], [role='tab'], input, textarea, select";
      return active.matches(control) && ring;
    });
    if (reached) return true;
  }
  return false;
}

for (const [screen, states] of Object.entries(STATES)) {
  for (const st of states) {
    test(`${screen} ${st}: renders and axe finds nothing serious`, async ({ page }) => {
      await page.goto(`/components/screens/${screen}?st=${st}&frame=1&static=1`);
      const board = page.locator(`[data-artboard='${st}']`);
      await expect(board).toBeVisible();
      expect(await seriousFindings(page, st)).toEqual([]);
      if (ACTIONABLE.has(st)) {
        expect(await reachesAControl(page, st), `${screen} ${st}: Tab reaches a control`).toBe(
          true,
        );
      }
    });
  }
}

test("AUD-11 b: Generate is disabled until a manager approves", async ({ page }) => {
  await page.goto("/components/screens/AUD-11?st=b&frame=1&static=1");
  const generate = page.getByRole("button", { name: /Generate item requests/ });
  await expect(generate).toBeDisabled();
});

test("AUD-31 e2: a mapping changed after sign-off says so", async ({ page }) => {
  await page.goto("/components/screens/AUD-31?st=e2&frame=1&static=1");
  await expect(page.getByText("Changed after sign-off").first()).toBeVisible();
});
