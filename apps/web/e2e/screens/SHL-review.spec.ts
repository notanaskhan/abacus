// P-04-T58: the review grammar's 44 artboards (SHL-09 a–f, SHL-10 a–g with e′, SHL-11 a–h,
// SHL-12 a–h with a′, SHL-15 a, a′, a″, b–e, SHL-16 a–f) in fixture mode at 1440×900, DPR 2,
// from the /components gallery: each renders, axe finds nothing serious or critical, and the
// keyboard suite checks Escape closes the topmost layer only, focus returns to the opener, and
// SHL-11's options are one radio group moved with the arrow keys. Tier C parity is the parity
// harness's (e2e/parity/screens.spec.ts reads the contracts' Parity tables).
// Run: `ABACUS_VISUAL=1 pnpm exec playwright test --project=chromium e2e/screens/SHL-review.spec.ts`.
import AxeBuilder from "@axe-core/playwright";
import { type Page, expect, test } from "@playwright/test";

const SERIOUS = new Set(["serious", "critical"]);

const ARTBOARDS: Readonly<Record<string, readonly string[]>> = {
  "SHL-09": ["a", "b", "c", "d", "e", "f"],
  "SHL-10": ["a", "b", "c", "d", "e", "ep", "f", "g"],
  "SHL-11": ["a", "b", "c", "d", "e", "f", "g", "h"],
  "SHL-12": ["a", "ap", "b", "c", "d", "e", "f", "g", "h"],
  "SHL-15": ["a", "ap", "app", "b", "c", "d", "e"],
  "SHL-16": ["a", "b", "c", "d", "e", "f"],
};

test.use({
  viewport: { width: 1440, height: 900 },
  deviceScaleFactor: 2,
  reducedMotion: "reduce",
});

async function open(page: Page, screen: string, st: string): Promise<void> {
  await page.goto(`/components/screens/${screen}?st=${st}&frame=1`);
  await expect(page.locator(`[data-artboard='${st}']`)).toBeAttached();
  // The artboard's own content or its portaled overlay, whichever the frame draws.
  await expect(page.locator("[data-overlay], [data-artboard] *").first()).toBeVisible();
}

test("the suite covers the 44 artboards", () => {
  expect(Object.values(ARTBOARDS).flat()).toHaveLength(44);
});

for (const [screen, states] of Object.entries(ARTBOARDS)) {
  for (const st of states) {
    test(`${screen}${st}: renders and axe finds nothing serious`, async ({ page }) => {
      await open(page, screen, st);
      const { violations } = await new AxeBuilder({ page }).analyze();
      const serious = violations
        .filter((v) => SERIOUS.has(v.impact ?? ""))
        .map((v) => `${v.id}: ${v.help} — ${v.nodes[0]?.target.join(" ") ?? ""}`);
      expect(serious).toEqual([]);
    });
  }
}

// --- keyboard ----------------------------------------------------------------------------------

/** The overlays a frame opens as layers (the inline e card and the SHL-15 detail blocks are not). */
const LAYERED: readonly [string, string][] = [
  ["SHL-10", "a"],
  ["SHL-11", "a"],
  ["SHL-12", "a"],
  ["SHL-15", "a"],
  ["SHL-16", "a"],
];

for (const [screen, st] of LAYERED) {
  test(`${screen}${st}: focus starts inside the layer and Tab stays in it`, async ({ page }) => {
    await open(page, screen, st);
    const layer = page.locator("[data-overlay]").last();
    await expect(layer).toBeVisible();
    for (let i = 0; i < 12; i += 1) {
      await page.keyboard.press("Tab");
      const inside = await layer.evaluate((el) => el.contains(document.activeElement));
      expect(inside).toBe(true);
    }
  });
}

test("SHL-12a: Escape closes only the topmost layer and focus returns to its opener", async ({
  page,
}) => {
  await open(page, "SHL-12", "a");
  const sheet = page.locator("[data-overlay]").last();
  await expect(sheet).toBeVisible();
  // Open the first nested popover or menu the sheet offers, then Escape once.
  const opener = sheet.locator("button[aria-haspopup], [aria-expanded='false']").first();
  if ((await opener.count()) === 0) test.skip(true, "no nested layer in this frame");
  await opener.focus();
  await page.keyboard.press("Enter");
  const before = await page.locator("[data-overlay]").count();
  await page.keyboard.press("Escape");
  await expect(page.locator("[data-overlay]")).toHaveCount(before - 1);
  await expect(sheet).toBeVisible();
  const back = await opener.evaluate((el) => el === document.activeElement);
  expect(back).toBe(true);
});

test("SHL-11a: the options are one radio group and the arrows move the choice", async ({
  page,
}) => {
  await open(page, "SHL-11", "a");
  const group = page.getByRole("radiogroup").first();
  await expect(group).toBeVisible();
  const radios = group.getByRole("radio");
  expect(await radios.count()).toBeGreaterThanOrEqual(2);
  const checked = group.getByRole("radio", { checked: true });
  await checked.focus();
  const first = await checked.getAttribute("value");
  await page.keyboard.press("ArrowDown");
  const moved = group.getByRole("radio", { checked: true });
  expect(await moved.getAttribute("value")).not.toBe(first);
  await page.keyboard.press("ArrowUp");
  expect(await group.getByRole("radio", { checked: true }).getAttribute("value")).toBe(first);
});

test("SHL-11b: the awaiting-role card's radios are disabled for Hannah", async ({ page }) => {
  await open(page, "SHL-11", "b");
  const radios = page.getByRole("radio");
  for (const radio of await radios.all()) await expect(radio).toBeDisabled();
});
