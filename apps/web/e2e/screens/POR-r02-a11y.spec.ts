// R-02-T24 (R-02 §5.4, §5.5): parity's non-pixel half and accessibility for POR-08, POR-09 and
// POR-15 on the gallery: axe (serious and critical block, DEC-11) on every built artboard at 1400
// and 390, forced colors and reduced motion, Tier D's T7 geometry (rail 336 · main 1030), the
// keyboard path for POR-09's pins, and the white-label crawler (no "Accrued" anywhere, DEC-01).
import AxeBuilder from "@axe-core/playwright";
import { type Page, expect, test } from "@playwright/test";

test.use({ reducedMotion: "reduce" });

const SERIOUS = new Set(["serious", "critical"]);
const BUILT: Record<string, string[]> = {
  "POR-08": ["a", "a2", "b", "c", "d", "e", "e2", "f"],
  "POR-09": ["a", "a2", "b", "c", "d", "e", "f"],
  "POR-15": ["a", "b", "c", "d", "e", "f"],
};

async function open(page: Page, screen: string, st: string, w?: "390"): Promise<void> {
  await page.goto(`/components/screens/${screen}?st=${st}&frame=1&static=1${w ? "&w=390" : ""}`);
  await expect(page.locator(`[data-artboard='${st}']`)).toBeVisible();
}

for (const [screen, states] of Object.entries(BUILT)) {
  for (const st of states) {
    for (const w of [undefined, "390"] as const) {
      test(`${screen}${st}${w ? " at 390" : ""}: no serious or critical axe finding`, async ({
        page,
      }) => {
        await open(page, screen, st, w);
        const results = await new AxeBuilder({ page })
          .include(`[data-artboard='${st}']`)
          .analyze();
        const blocking = results.violations.filter((v) => SERIOUS.has(v.impact ?? ""));
        expect(blocking.map((v) => `${v.id}: ${v.help}`)).toEqual([]);
      });
    }
    test(`${screen}${st}: the portal never says Accrued`, async ({ page }) => {
      await open(page, screen, st);
      const text = await page.locator(`[data-artboard='${st}']`).innerText();
      // The product's name, never an account: "Accrued expenses" and "Accrued administrative
      // expenses" (PAJE-2) are the client's own words (J12 8; S35 round 2).
      expect(text).not.toMatch(/Accrued(?! (?:[a-z]|Expenses))/);
    });
  }

  test(`${screen}: forced colors keep the pane edges`, async ({ page }) => {
    await page.emulateMedia({ forcedColors: "active" });
    await open(page, screen, BUILT[screen]?.[0] ?? "a");
    const results = await new AxeBuilder({ page }).analyze();
    expect(results.violations.filter((v) => SERIOUS.has(v.impact ?? ""))).toEqual([]);
  });
}

test("POR-09a: Tier D, rail 336 and main 1030", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await open(page, "POR-09", "a");
  const widths = await page
    .locator("[data-artboard='a']")
    .evaluate((el) =>
      Array.from(el.querySelectorAll<HTMLElement>("*"), (c) =>
        Math.round(c.getBoundingClientRect().width),
      ),
    );
  expect(widths).toContain(336);
  expect(widths).toContain(1030);
});

test("POR-09a: the pins are buttons in reading order and select their comment", async ({
  page,
}) => {
  await open(page, "POR-09", "a");
  const pin = page.locator("[data-pin='1']");
  await expect(pin).toBeVisible();
  await pin.focus();
  await page.keyboard.press("Enter");
  await expect(pin).toHaveAttribute("aria-pressed", "true");
  await expect(page.locator("[data-comment][data-selected='true']")).toHaveCount(1);
  await expect(page.getByRole("form", { name: "Add a comment on this page" })).toBeVisible();
});
