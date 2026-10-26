// SHL-14 a, b, e, f (P-06-T13) and d (P-06-T24) in fixture mode (build-screen-from-handoff §5):
// every scenario at 1440×900, DPR 2, from the /components gallery on fixtures, with axe at zero
// serious or critical findings inside the drawer. Tier C parity is reported by the parity harness (P-06-T26).
// Run: `ABACUS_VISUAL=1 pnpm exec playwright test --project=chromium e2e/screens/SHL-14.spec.ts`.
import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const SERIOUS = new Set(["serious", "critical"]);

const STATES = [
  { st: "a", ready: "Adds 1 request · Source Documents will read 11 of 25 received" },
  { st: "b", ready: "Requested Sep 1 · due Sep 25" },
  { st: "e", ready: "Add a due date to send" },
  { st: "f", ready: "Approve & send to Luis Ferrante" },
  { st: "d", ready: "Pending incorporation" },
] as const;

test.use({
  viewport: { width: 1440, height: 900 },
  deviceScaleFactor: 2,
  reducedMotion: "reduce",
});

for (const { st, ready } of STATES) {
  test(`SHL-14${st}: renders and axe finds nothing serious`, async ({ page }) => {
    await page.goto(`/components/screens/SHL-14?st=${st}&frame=1`);
    const drawer = page.getByRole("dialog");
    await expect(drawer).toBeVisible();
    await expect(drawer.getByText(ready).first()).toBeVisible();
    const { violations } = await new AxeBuilder({ page }).include("[role='dialog']").analyze();
    const serious = violations
      .filter((v) => SERIOUS.has(v.impact ?? ""))
      .map((v) => `${v.id}: ${v.help} — ${v.nodes[0]?.target.join(" ") ?? ""}`);
    expect(serious).toEqual([]);
  });
}
