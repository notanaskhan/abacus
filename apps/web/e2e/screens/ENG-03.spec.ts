// ENG-03 a–h in fixture mode (P-07-T21, P-07-T34; build-screen-from-handoff §5): every scenario at
// 1440×900, DPR 2, from the /components gallery on fixtures, with axe at zero serious or critical
// findings inside the wizard. Tier C parity is reported by the parity harness (P-07-T63).
// Run: `ABACUS_VISUAL=1 pnpm exec playwright test --project=chromium e2e/screens/ENG-03.spec.ts`.
import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const SERIOUS = new Set(["serious", "critical"]);

const ARTBOARDS = [
  { st: "a", ready: "G1 Continuance approved — Margaret Okonkwo · Aug 28, 2026" },
  { st: "b", ready: "GAAS nonissuer · periods ending 12/31/2025 · AU-C 703" },
  { st: "c", ready: "EQR eligible — not on team, no cooling-off conflict" },
  { st: "d", ready: "Acceptance is not approved yet (G1)." },
  { st: "e", ready: "§7216 consents" },
  { st: "f", ready: "Single audit" },
  { st: "g", ready: "Group audit (SAS 149)" },
  { st: "h", ready: "SSAE · AT-C 205" },
] as const;

test.use({
  viewport: { width: 1440, height: 900 },
  deviceScaleFactor: 2,
  reducedMotion: "reduce",
});

for (const { st, ready } of ARTBOARDS) {
  test(`ENG-03${st}: renders and axe finds nothing serious`, async ({ page }) => {
    await page.goto(`/components/screens/ENG-03?st=${st}&frame=1`);
    const wizard = page.getByRole("dialog");
    await expect(wizard).toBeVisible();
    await expect(wizard.getByText(ready).first()).toBeVisible();
    if (st === "d") await expect(wizard.getByRole("button", { name: "Next" })).toBeDisabled();
    if (st === "f") {
      await wizard.getByText("Single audit").hover();
      await expect(
        page.getByText("Not in this release. Run single audits outside Accrued for now.").first(),
      ).toBeVisible();
    }
    const { violations } = await new AxeBuilder({ page }).include("[role='dialog']").analyze();
    const serious = violations
      .filter((v) => SERIOUS.has(v.impact ?? ""))
      .map((v) => `${v.id}: ${v.help} — ${v.nodes[0]?.target.join(" ") ?? ""}`);
    expect(serious).toEqual([]);
  });
}
