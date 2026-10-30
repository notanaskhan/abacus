// F-06-T12: independent acceptance tests for the portal mobile specimen at 390 (ADR-078; F-06
// row): every target 44 × 44, no Accrued text or blue, and zero serious axe findings with the
// viewport at 390 px. Scoped to the TPL-19 section of the /components gallery (fixtures only).
// Run: `ABACUS_VISUAL=1 pnpm exec playwright test --project=chromium e2e/screens/TPL-19.spec.ts`.
import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const SERIOUS = new Set(["serious", "critical"]);
const FRAMES = ["tpl-19-1", "tpl-19-2", "tpl-19-5", "tpl-19-6-ring", "tpl-19-6", "tpl-19-7"];

test.use({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 1, reducedMotion: "reduce" });

test.beforeEach(async ({ page }) => {
  await page.goto("/components?frame=1&static=1");
  await expect(page.locator("section#tpl-19")).toBeAttached();
});

test("axe at 390: nothing serious or critical in any TPL-19 frame", async ({ page }) => {
  for (const id of FRAMES) {
    const { violations } = await new AxeBuilder({ page })
      .include(`section#tpl-19 [data-artboard="${id}"]`)
      .analyze();
    const serious = violations
      .filter((v) => SERIOUS.has(v.impact ?? ""))
      .map((v) => `${id} ${v.id}: ${v.nodes[0]?.target.join(" ") ?? ""}`);
    expect(serious).toEqual([]);
  }
});

test("every target is at least 44 × 44", async ({ page }) => {
  for (const id of FRAMES) {
    const frame = page
      .locator(`section#tpl-19 [data-artboard="${id}"] [data-frame="phone"]`)
      .first();
    await frame.scrollIntoViewIfNeeded();
    const small = await frame.evaluate((root) =>
      [
        ...root.querySelectorAll(
          "button, a[href], [role='tab'], [role='menuitem'], select, label[for]",
        ),
      ]
        .filter((el) => (el as HTMLElement).offsetParent !== null)
        .map((el) => ({ el, b: el.getBoundingClientRect() }))
        .filter(({ b }) => b.width > 0 && (b.width < 44 || b.height < 44))
        .map(
          ({ el, b }) =>
            `${(el.getAttribute("aria-label") ?? (el as HTMLElement).innerText).trim().slice(0, 40)} ${String(Math.round(b.width))}×${String(Math.round(b.height))}`,
        ),
    );
    expect([id, small]).toEqual([id, []]);
  }
});

test("no Accrued text and no blue anywhere in TPL-19", async ({ page }) => {
  const section = page.locator("section#tpl-19");
  await expect(section).not.toContainText("Accrued");
  const blue = await section.evaluate(
    (root) =>
      [...root.querySelectorAll<HTMLElement>("*")].filter((el) => {
        const s = getComputedStyle(el);
        return [s.color, s.backgroundColor, s.borderTopColor].some((c) => {
          const m = /rgba?\((\d+),\s*(\d+),\s*(\d+)/u.exec(c);
          if (m === null) return false;
          const [r, g, b] = [Number(m[1]), Number(m[2]), Number(m[3])];
          return b > 150 && b - Math.max(r, g) > 60;
        });
      }).length,
  );
  expect(blue).toBe(0);
});
