// ac-test-author: ayushkbhatia
// F-06-T07 (ADR-078; F-06.md Stories 1.1 to 1.6): TPL-16 b, d, e, f, g, pending and TPL-19 frame 9
// in fixture mode from the /components gallery, axe at zero serious or critical findings; at 390
// nothing scrolls sideways, every control has a 44 by 44 target, and the sticky bar never covers
// the active field. Run: `ABACUS_VISUAL=1 pnpm exec playwright test --project=chromium
// e2e/screens/TPL-16.spec.ts`.
import AxeBuilder from "@axe-core/playwright";
import { type Page, expect, test } from "@playwright/test";

const SERIOUS = new Set(["serious", "critical"]);

async function axeClean(page: Page, scope: string): Promise<void> {
  const { violations } = await new AxeBuilder({ page }).include(scope).analyze();
  const serious = violations
    .filter((v) => SERIOUS.has(v.impact ?? ""))
    .map((v) => `${v.id}: ${v.help} — ${v.nodes[0]?.target.join(" ") ?? ""}`);
  expect(serious).toEqual([]);
}

test.describe("TPL-16 at 1440", () => {
  test.use({
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 2,
    reducedMotion: "reduce",
  });
  for (const st of ["b", "d", "e", "f", "pending"]) {
    test(`TPL-16${st}: axe finds nothing serious`, async ({ page }) => {
      await page.goto(`/components/screens/TPL-16?st=${st}&frame=1`);
      await expect(page.locator("[data-template='t16']")).toBeVisible();
      await axeClean(page, "[data-artboard]");
    });
  }
});

test.describe("at 390", () => {
  test.use({
    viewport: { width: 390, height: 844 },
    deviceScaleFactor: 3,
    reducedMotion: "reduce",
  });
  for (const path of ["/components/screens/TPL-16?st=g", "/components/screens/TPL-19?st=9"]) {
    test(`${path}: no sideways scroll, 44 targets, the bar never covers the active field`, async ({
      page,
    }) => {
      await page.goto(path);
      const column = page.locator("[data-layout='phone']");
      await expect(column).toBeVisible();
      const wide = await page.evaluate(
        () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
      );
      expect(wide).toBe(false);
      const small = await page.evaluate(() =>
        [
          ...document.querySelectorAll<HTMLElement>(
            "[data-layout='phone'] button, [data-signing='mobile-sign-bar'] button",
          ),
        ]
          .filter((b) => b.offsetParent !== null && b.getAttribute("aria-hidden") !== "true")
          .map((b) => {
            const r = b.getBoundingClientRect();
            const before = getComputedStyle(b, "::before");
            const h = Math.max(r.height, Number.parseFloat(before.height) || 0);
            return { name: b.getAttribute("aria-label") ?? b.textContent, w: r.width, h };
          })
          .filter((t) => t.h < 44 || t.w < 44),
      );
      expect(small).toEqual([]);
      const field = page.getByRole("button", { name: /^Sign here:/ }).first();
      await field.focus();
      const bar = await page.locator("[data-signing='mobile-sign-bar']").boundingBox();
      const box = await field.boundingBox();
      expect(bar).not.toBeNull();
      expect(box).not.toBeNull();
      if (bar !== null && box !== null) expect(box.y + box.height).toBeLessThanOrEqual(bar.y);
      await axeClean(page, "[data-layout='phone']");
    });
  }
});
