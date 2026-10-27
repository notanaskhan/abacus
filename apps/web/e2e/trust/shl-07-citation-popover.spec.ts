// P-03-T24 (TASK-1441): SHL-07 a–e in fixture mode, from the /components gallery (no API, no
// database). Per artboard: axe at zero serious or critical findings; the Tier D computed-style
// assertions P-03 §5.5 makes blocking (popover 372 wide, 420 for guidance, radius 12); the
// keyboard path of §5.6 (a pinned popover takes focus, Escape closes it and returns focus to the
// cell; the stepper is named and announces "Source 2 of 3"); and reduced motion (§5.6: the 260 ms
// rise is off). Tier C parity locking is the parity harness's and a human sign-off, not this spec.
// Run: `ABACUS_VISUAL=1 pnpm exec playwright test --project=chromium e2e/trust/shl-07-citation-popover.spec.ts`.
import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Locator, type Page } from "@playwright/test";

const SERIOUS = new Set(["serious", "critical"]);
const POPOVER = '[data-popover="anchored"]';
const STATES = ["a", "b", "c", "d", "e"] as const;
type State = (typeof STATES)[number];
const WIDTH: Record<State, number> = { a: 372, b: 372, c: 420, d: 372, e: 372 };

test.use({
  viewport: { width: 1440, height: 900 },
  deviceScaleFactor: 2,
  reducedMotion: "reduce",
});

async function open(page: Page, st: State): Promise<Locator> {
  await page.goto(`/components/screens/SHL-07?st=${st}&frame=1`);
  const popover = page.locator(POPOVER).first();
  await expect(popover).toBeVisible();
  return popover;
}

async function serious(page: Page): Promise<string[]> {
  const { violations } = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();
  return violations
    .filter((v) => SERIOUS.has(v.impact ?? ""))
    .map((v) => `${v.id}: ${v.help} — ${v.nodes[0]?.target.join(" ") ?? ""}`);
}

for (const st of STATES) {
  test(`SHL-07${st}: axe AA finds nothing serious`, async ({ page }) => {
    await open(page, st);
    expect(await serious(page)).toEqual([]);
  });

  test(`SHL-07${st}: Tier D, ${String(WIDTH[st])} wide with radius 12`, async ({ page }) => {
    const popover = await open(page, st);
    const box = await popover.boundingBox();
    expect(box?.width).toBe(WIDTH[st]);
    // The surface that draws the popover: the host or the full-width box inside it.
    const radii = await popover.evaluate((el) => {
      const width = Math.round(el.getBoundingClientRect().width);
      return [el, ...Array.from(el.querySelectorAll<HTMLElement>("*"))]
        .filter((n) => Math.round(n.getBoundingClientRect().width) === width)
        .map((n) => getComputedStyle(n).borderTopLeftRadius)
        .filter((r) => r !== "0px");
    });
    expect(radii[0]).toBe("12px");
  });

  test(`SHL-07${st}: reduced motion leaves no rise or fade running`, async ({ page }) => {
    const popover = await open(page, st);
    const motion = await popover.evaluate((el) => {
      const all = [el, ...Array.from(el.querySelectorAll<HTMLElement>("*"))];
      return all
        .map((n) => getComputedStyle(n))
        .filter((s) => {
          const seconds = (v: string) => Math.max(...v.split(",").map((p) => parseFloat(p) || 0));
          return (
            (s.animationName !== "none" && seconds(s.animationDuration) > 0.01) ||
            seconds(s.transitionDuration) > 0.01
          );
        }).length;
    });
    expect(motion).toBe(0);
  });
}

test("SHL-07a: by keyboard, Enter pins a named dialog and Escape returns focus to the cell", async ({
  page,
}) => {
  await open(page, "a");
  await page.keyboard.press("Escape"); // the artboard opens pinned; start from the closed cell
  await expect(page.locator(POPOVER)).toHaveCount(0);
  const cell = page.locator("[data-cited]").first();
  await cell.focus();
  await expect(cell).toBeFocused();
  await page.keyboard.press("Enter");
  // A named, non-modal dialog (§5.6) that takes focus once pinned.
  const dialog = page.getByRole("dialog", { name: /\S/ }).first();
  await expect(dialog).toBeVisible();
  expect(await dialog.getAttribute("aria-modal")).not.toBe("true");
  await expect(page.locator("[data-pinned]").first()).toBeAttached();
  await page.keyboard.press("Escape");
  await expect(page.locator(POPOVER)).toHaveCount(0);
  await expect(cell).toBeFocused();
});

test("SHL-07a: a popover pinned by keyboard takes focus", async ({ page }) => {
  await open(page, "a");
  await page.keyboard.press("Escape");
  const cell = page.locator("[data-cited]").first();
  await cell.focus();
  await page.keyboard.press("Enter");
  await expect(page.locator("[data-pinned]").first()).toBeAttached();
  await expect
    .poll(
      () =>
        page
          .locator(POPOVER)
          .first()
          .evaluate((el) => el.contains(document.activeElement)),
      { timeout: 3000 },
    )
    .toBe(true);
});

test("SHL-07b: the stepper is named and announces Source 2 of 3", async ({ page }) => {
  const popover = await open(page, "b");
  const next = popover.getByRole("button", { name: "Next source" });
  await expect(popover.getByRole("button", { name: "Previous source" })).toBeVisible();
  await next.focus();
  await page.keyboard.press("Enter");
  await expect(popover.getByText("2 / 3")).toBeVisible();
  // Announced in words, not only drawn as "2 / 3" (§5.6).
  await expect(
    page.locator("[aria-live], [role='status']").filter({ hasText: "Source 2 of 3" }),
  ).toHaveCount(1);
});

test("SHL-07d: the hover preview never takes focus", async ({ page }) => {
  await open(page, "d");
  const focusInside = await page
    .locator(POPOVER)
    .first()
    .evaluate((el) => el.contains(document.activeElement));
  expect(focusInside).toBe(false);
});

test("SHL-07e: a moved source offers Re-link… by keyboard", async ({ page }) => {
  const popover = await open(page, "e");
  await expect(popover.getByText(/Source moved/)).toBeVisible();
  const relink = popover.getByRole("button", { name: /Re-link/ });
  await expect(relink).toBeVisible();
  await relink.focus();
  await expect(relink).toBeFocused();
});
