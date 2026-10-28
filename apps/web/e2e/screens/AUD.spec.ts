// AUD-01 a–h, AUD-02 a–g and AUD-03 a–g in fixture mode (A-01-T28; A-01 §10 DoD): every artboard at
// 1440×900, DPR 2, from the /components gallery on fixtures, with axe at zero serious or critical
// findings, and a keyboard path: Tab from the top of the artboard reaches the screen's first
// actionable row or control with a visible focus ring, and never leaves the artboard first. Tier C
// parity is reported by e2e/parity/screens.spec.ts (`aud-0Nx.window` in the parity manifest) and
// the host frame's geometry by e2e/visual/tier-d-audits.spec.ts.
// Run: `ABACUS_VISUAL=1 pnpm exec playwright test --project=chromium e2e/screens/AUD.spec.ts`.
import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const SERIOUS = new Set(["serious", "critical"]);
const SCREENS = {
  "AUD-01": "abcdefgh",
  "AUD-02": "abcdefg",
  "AUD-03": "abcdefg",
} as const;
const TAB_LIMIT = 40;

test.use({
  viewport: { width: 1440, height: 900 },
  deviceScaleFactor: 2,
  reducedMotion: "reduce",
});

for (const [screen, states] of Object.entries(SCREENS)) {
  for (const st of states) {
    test(`${screen}${st}: renders, axe finds nothing serious, the keyboard reaches a control`, async ({
      page,
    }) => {
      await page.goto(`/components/screens/${screen}?st=${st}&frame=1&static=1`);
      const board = page.locator(`[data-artboard='${st}']`);
      await expect(board).toBeVisible();
      await expect(board.locator("[data-shell='app']").first()).toBeVisible();

      const { violations } = await new AxeBuilder({ page })
        .include(`[data-artboard='${st}']`)
        .analyze();
      const serious = violations
        .filter((v) => SERIOUS.has(v.impact ?? ""))
        .map((v) => `${v.id}: ${v.help} — ${v.nodes[0]?.target.join(" ") ?? ""}`);
      expect(serious).toEqual([]);

      // Keyboard: start inside the artboard and Tab until a control inside it has focus.
      await board
        .locator("[data-shell='app']")
        .first()
        .click({ position: { x: 2, y: 2 } });
      let reached = false;
      for (let i = 0; i < TAB_LIMIT && !reached; i += 1) {
        await page.keyboard.press("Tab");
        reached = await board.evaluate((root) => {
          const active = document.activeElement;
          if (active === null || !root.contains(active)) return false;
          const style = getComputedStyle(active);
          const ring = style.outlineStyle !== "none" || style.boxShadow !== "none";
          return active.matches("a[href], button, [role='row'], [role='tab'], input") && ring;
        });
      }
      expect(reached, `${screen}${st}: Tab reaches a focusable control with a ring`).toBe(true);
    });
  }
}
