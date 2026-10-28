// R-01-T31: the portal PBC screens under forced colours and reduced motion. Every state of POR-03
// (a–i, c2, motion, M), POR-04 (a–g) and POR-14 (a–f), from the /components gallery on fixtures,
// with Windows High Contrast emulated (`forced-colors: active`) and motion reduced: axe finds
// nothing serious or critical, nothing animates (the drop ring and the sort motion are static under
// reduced motion, POR-03 contract), and no state draws "Accrued". The plain-colour runs at 1400
// and 390 are each screen's own spec; the keyboard-only drop and sheet paths are
// e2e/journeys/portal-keyboard.spec.ts.
// Run: `ABACUS_VISUAL=1 pnpm exec playwright test --project=chromium e2e/screens/portal-a11y.spec.ts`.
import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const SERIOUS = new Set(["serious", "critical"]);

const SCREENS = [
  {
    id: "POR-03",
    states: ["a", "b", "motion", "c", "c2", "d", "e", "f", "g", "h", "i", "M"],
  },
  { id: "POR-04", states: ["a", "b", "c", "d", "e", "f", "g"] },
  { id: "POR-14", states: ["a", "b", "c", "d", "e", "f"] },
] as const;

test.use({
  viewport: { width: 1440, height: 900 },
  deviceScaleFactor: 1,
  reducedMotion: "reduce",
  forcedColors: "active",
});

for (const { id, states } of SCREENS) {
  for (const st of states) {
    test(`${id}${st}: forced colours and reduced motion, axe finds nothing serious`, async ({
      page,
    }) => {
      await page.goto(`/components/screens/${id}?st=${st}&frame=1`);
      const board = page.locator(`[data-artboard='${st}']`);
      await expect(board).toBeVisible();
      expect(await page.evaluate(() => matchMedia("(forced-colors: active)").matches)).toBe(true);
      // Nothing moves once the state has settled: a running animation would ignore the preference.
      await page.waitForTimeout(400);
      const running = await page.evaluate(
        () =>
          document
            .getAnimations()
            .filter(
              (a) => a.playState === "running" && a.effect?.getTiming().iterations === Infinity,
            ).length,
      );
      expect(running, "infinite animations under reduced motion").toBe(0);
      expect(await board.innerText()).not.toMatch(/accrued/i);
      // POR-04's sheet is a modal in its own layer, outside the artboard: scanned with it.
      const sheets = await page.getByRole("dialog").count();
      if (sheets > 0) {
        expect(await page.getByRole("dialog").first().innerText()).not.toMatch(/accrued/i);
      }
      let axe = new AxeBuilder({ page }).include(`[data-artboard='${st}']`);
      if (sheets > 0) axe = axe.include("[role='dialog']");
      const { violations } = await axe.analyze();
      const serious = violations
        .filter((v) => SERIOUS.has(v.impact ?? ""))
        .map((v) => `${v.id}: ${v.help} — ${v.nodes[0]?.target.join(" ") ?? ""}`);
      expect(serious).toEqual([]);
    });
  }
}
