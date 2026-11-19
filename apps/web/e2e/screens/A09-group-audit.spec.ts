// A-09-T42 (TASK-8702; A-09 §10.1): the group audit's screens in fixture mode, every artboard at
// 1440×900, DPR 2, from the /components gallery, with axe at zero serious or critical findings in
// the frame and in any overlay the state opens. AUD-31's group states (a-e) wait on A-09; its
// single-entity states are A03-sampling-mapping.spec.ts's. POR-23 never shows the product's name.
// Run: `ABACUS_VISUAL=1 pnpm exec playwright test --project=chromium e2e/screens/A09-group-audit.spec.ts`.
import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { PRODUCT_NAME } from "../harness/invariants";

const SERIOUS = new Set(["serious", "critical"]);
const SCREENS: Readonly<Record<string, readonly string[]>> = {
  "AUD-32": ["a", "b", "c", "d", "e", "f"],
  "AUD-33": ["a", "b", "c", "d", "e", "f", "g"],
  "AUD-34": ["a", "b", "c", "d", "e", "f"],
  "AUD-35": ["a", "b", "c", "d", "e", "f", "g"],
  "POR-23": ["a", "b", "c", "d", "e", "f"],
};

test.use({
  viewport: { width: 1440, height: 900 },
  deviceScaleFactor: 2,
  reducedMotion: "reduce",
});

for (const [screen, states] of Object.entries(SCREENS)) {
  for (const st of states) {
    test(`${screen}${st}: renders and axe finds nothing serious`, async ({ page }) => {
      await page.goto(`/components/screens/${screen}?st=${st}&frame=1`);
      const board = page.locator(`[data-artboard='${st}']`).first();
      await expect(board).toBeVisible();
      await expect(board.locator("[aria-busy='true']")).toHaveCount(0);
      let builder = new AxeBuilder({ page })
        .setLegacyMode(true)
        .include(`[data-artboard='${st}']`);
      if ((await page.locator("[role='dialog']").count()) > 0)
        builder = builder.include("[role='dialog']");
      const { violations } = await builder.analyze();
      const serious = violations
        .filter((v) => SERIOUS.has(v.impact ?? ""))
        .map((v) => `${v.id}: ${v.help} — ${v.nodes[0]?.target.join(" ") ?? ""}`);
      expect(serious).toEqual([]);
      if (screen === "POR-23") expect(await board.innerText()).not.toMatch(PRODUCT_NAME);
    });
  }
}
