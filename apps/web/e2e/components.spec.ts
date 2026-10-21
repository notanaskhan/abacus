// SPEC-048 AC-3, AC-4, AC-10 (F-05-T09): axe on /components/** under the AA ladder, and the
// gallery's contrast parameter. The gallery calls no API, so only the dev server is needed
// (`make dev-fixtures` or `make dev`).
import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

async function expectNoSeriousViolations(page: Page): Promise<void> {
  const { violations } = await new AxeBuilder({ page }).analyze();
  const serious = violations.filter((v) => v.impact === "serious" || v.impact === "critical");
  expect(
    serious.map((v) => `${v.id} (${v.impact ?? "?"}): ${v.help}`),
    "serious or critical accessibility violations",
  ).toEqual([]);
}

test("ac3: axe finds nothing serious on /components/**", async ({ page }) => {
  await page.goto("/components");
  await expect(page.getByRole("heading", { name: "Components", level: 1 })).toBeVisible();
  await expectNoSeriousViolations(page);

  await page.goto("/components/tokens");
  await expect(page.getByRole("table", { name: /Every colour token/ })).toBeVisible();
  await expectNoSeriousViolations(page);

  await page.goto("/components/icons");
  await expect(page.getByRole("table", { name: /Every registered icon name/ })).toBeVisible();
  await expectNoSeriousViolations(page);

  await page.goto("/components/screens/NO-SUCH-SCREEN");
  await expect(page.getByText("Not built")).toBeVisible();
  await expectNoSeriousViolations(page);
});

test("ac4: ?contrast=reference sets data-contrast on <html>", async ({ page }) => {
  await page.goto("/components/tokens");
  await expect(page.getByRole("table", { name: /Every colour token/ })).toBeVisible();
  await expect(page.locator("html")).not.toHaveAttribute("data-contrast", /.*/);
  await page.goto("/components/tokens?contrast=reference");
  await expect(page.locator("html")).toHaveAttribute("data-contrast", "reference");
});

test("ac15: /_ds no longer routes", async ({ page }) => {
  await page.goto("/_ds");
  await expect(page.getByText("Page not found")).toBeVisible();
});

// F-05-T14 (SPEC-048 AC-8): reduced motion leaves document.getAnimations() empty. The CSS block in
// motion.css cuts what a media query can; useReducedMotion() makes the kit's own components render
// no animation at all. The gallery calls no API, so only the dev server is needed.
async function runningAnimations(page: Page): Promise<string[]> {
  return page.evaluate(() =>
    document.getAnimations().map((a) => {
      const named = a as Animation & { animationName?: string; transitionProperty?: string };
      return named.animationName ?? named.transitionProperty ?? a.id;
    }),
  );
}

test.describe("motion", () => {
  test.describe("with reduced motion", () => {
    test.use({ reducedMotion: "reduce" });

    test("ac8: no animation runs on /components/**", async ({ page }) => {
      for (const path of ["/components", "/components/tokens", "/components/icons"]) {
        await page.goto(path);
        await expect(page.getByRole("heading", { name: "Components", level: 1 })).toBeVisible();
        await page.evaluate(() => document.fonts.ready);
        await expect.poll(() => runningAnimations(page), { message: path }).toEqual([]);
      }
    });

    test("ac8: the motion specimens draw their still form", async ({ page }) => {
      await page.goto("/components");
      await expect(page.getByTestId("reduced-motion-state")).toContainText("Reduced motion is on");
      await expect(page.locator("[data-spinner='turning']")).toHaveCount(0);
      await expect(page.locator("[data-typing='beating']")).toHaveCount(0);
      await expect(page.locator("[data-reveal='rising']")).toHaveCount(0);
      await expect(page.locator("[data-pulse='skeleton'], [data-pulse='breathe']")).toHaveCount(0);
      await expect.poll(() => runningAnimations(page)).toEqual([]);
    });
  });

  test.describe("with motion allowed", () => {
    test.use({ reducedMotion: "no-preference" });

    test("ac8: the same specimens do animate, so the check above bites", async ({ page }) => {
      await page.goto("/components");
      await expect(page.getByTestId("reduced-motion-state")).toContainText("Motion is on");
      await expect.poll(async () => (await runningAnimations(page)).length).toBeGreaterThan(0);
      const names = new Set(await runningAnimations(page));
      for (const name of ["ac-spin", "ac-pulse", "ac-breathe", "ac-typing"]) {
        expect(names, name).toContain(name);
      }
    });
  });
});
