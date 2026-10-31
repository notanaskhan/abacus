// TXP-12 A–F (T-02-T25) in fixture mode: every scenario at 1440×900, DPR 2, from the
// /components gallery on fixtures, with axe at zero serious or critical findings in the frame.
// Run: `ABACUS_VISUAL=1 pnpm exec playwright test --project=chromium e2e/screens/TXP-12.spec.ts`.
import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const SERIOUS = new Set(["serious", "critical"]);

const ARTBOARDS: readonly { st: string; ready: string }[] = [
  { st: "a", ready: "Release blocked: final approval" },
  { st: "a2", ready: "Box 2 307,900" },
  { st: "a3", ready: "domestic filing exception unavailable" },
  { st: "a4", ready: "Drafts block final approval of the receiving return." },
  { st: "a5", ready: "Portal · My K-1s (POR-13), with an invite email to each recipient" },
  { st: "b", ready: "Invite email bounced — update address" },
  { st: "b2", ready: "Resend K-1" },
  { st: "c", ready: "Arjun Mehta" },
  { st: "d", ready: "Nora Calloway" },
  { st: "e", ready: "Superseded (amended K-1)" },
  { st: "f", ready: "No K-1s yet." },
];

test.use({
  viewport: { width: 1440, height: 900 },
  deviceScaleFactor: 2,
  reducedMotion: "reduce",
});

for (const { st, ready } of ARTBOARDS) {
  test(`TXP-12${st}: renders and axe finds nothing serious`, async ({ page }) => {
    await page.goto(`/components/screens/TXP-12?st=${st}&frame=1`);
    const board = page.locator(`[data-artboard='${st}']`);
    await expect(board).toBeVisible();
    await expect(page.getByText(ready).first()).toBeVisible();
    const { violations } = await new AxeBuilder({ page })
      .include(`[data-artboard='${st}']`)
      .analyze();
    const serious = violations
      .filter((v) => SERIOUS.has(v.impact ?? ""))
      .map((v) => `${v.id}: ${v.help} — ${v.nodes[0]?.target.join(" ") ?? ""}`);
    expect(serious).toEqual([]);
  });
}
