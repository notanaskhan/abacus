// POR-01 a, b, e, f, g and the 390 layout in fixture mode (P-08-T09; portal-screen skill): every
// artboard from the /components gallery on fixtures (no API, no database), axe at zero serious or
// critical findings at 1400, 720 and 390, and the white-label rule: no product name in the text or
// in any attribute a person or assistive technology meets. Tier C parity is P-08-T27's.
// Run: `ABACUS_VISUAL=1 pnpm exec playwright test --project=chromium e2e/screens/POR-01.spec.ts`.
import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const SERIOUS = new Set(["serious", "critical"]);

const ARTBOARDS = [
  { st: "a", ready: "Sign in to your client portal" },
  { st: "b", ready: "Check your email" },
  { st: "e", ready: "This sign-in link has expired" },
  { st: "f", ready: "Check your email" },
  { st: "g", ready: "Too many attempts" },
  { st: "M", ready: "Sign in to your client portal" },
] as const;

const WIDTHS = [1400, 720, 390] as const;

for (const width of WIDTHS) {
  for (const { st, ready } of ARTBOARDS) {
    test(`POR-01${st} at ${String(width)}: renders, axe clean, white-label`, async ({ page }) => {
      await page.setViewportSize({ width, height: 900 });
      await page.goto(`/components/screens/POR-01?st=${st}&frame=1`);
      const board = page.locator(`[data-artboard='${st}']`);
      await expect(board).toBeVisible();
      await expect(page.getByRole("heading", { name: ready })).toBeVisible();
      const leaks = await board.evaluate((el) => {
        const found: string[] = [];
        if (/accrued/i.test((el as HTMLElement).innerText)) found.push("text");
        for (const node of el.querySelectorAll("*")) {
          for (const name of ["aria-label", "title", "alt", "placeholder"]) {
            const value = node.getAttribute(name);
            if (value !== null && /accrued/i.test(value)) found.push(`${name}="${value}"`);
          }
        }
        return found;
      });
      expect(leaks).toEqual([]);
      const { violations } = await new AxeBuilder({ page })
        .include(`[data-artboard='${st}']`)
        .analyze();
      const serious = violations
        .filter((v) => SERIOUS.has(v.impact ?? ""))
        .map((v) => `${v.id}: ${v.help} — ${v.nodes[0]?.target.join(" ") ?? ""}`);
      expect(serious).toEqual([]);
    });
  }
}
