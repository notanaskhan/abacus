// P-03-T24 (TASK-1441): SHL-08 a–f and h in fixture mode, from the /components gallery (no API,
// no database). Per artboard: axe AA at zero serious or critical findings; the Tier D
// computed-style assertions P-03 §5.5 makes blocking (drawer 480 wide, header 46 high with a
// 14.5 px / 500 title; dock pane 330; toolbar buttons 26 px; linked-figure rows 36 px); keyboard
// reach of the toolbar and the unlock form (§5.6); and reduced motion (the light, fade and
// skeleton pulse off). Tier C parity locking is the parity harness's and a human sign-off, not
// this spec.
// Run: `ABACUS_VISUAL=1 pnpm exec playwright test --project=chromium e2e/trust/shl-08-source-viewer.spec.ts`.
import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Locator, type Page } from "@playwright/test";

const SERIOUS = new Set(["serious", "critical"]);
const STATES = ["a", "b", "c", "d", "e", "f", "h"] as const;
type State = (typeof STATES)[number];
const DRAWER_STATES: readonly State[] = ["a", "c", "d", "e", "f", "h"];

test.use({
  viewport: { width: 1440, height: 900 },
  deviceScaleFactor: 2,
  reducedMotion: "reduce",
});

async function open(page: Page, st: State): Promise<void> {
  await page.goto(`/components/screens/SHL-08?st=${st}&frame=1`);
  await expect(
    page.locator("[data-overlay], [data-viewer-bar], input[type='password']").first(),
  ).toBeVisible();
}

/** The O2 drawer, held open on the artboard (a labelled complementary region). */
function drawer(page: Page): Locator {
  return page.locator("[data-overlay]").first();
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
  test(`SHL-08${st}: axe AA finds nothing serious`, async ({ page }) => {
    await open(page, st);
    expect(await serious(page)).toEqual([]);
  });

  test(`SHL-08${st}: toolbar buttons are 26 px and every one is named`, async ({ page }) => {
    await open(page, st);
    const bars = page.locator("[data-viewer-bar]");
    if (st === "e" || st === "d") {
      // Loading and locked show no page toolbar to measure.
      return;
    }
    await expect(bars.first()).toBeVisible();
    const buttons = await bars.locator("button").evaluateAll((els) =>
      els
        .filter((e) => (e as HTMLElement).offsetParent !== null)
        .map((e) => ({
          height: e.getBoundingClientRect().height,
          name: e.getAttribute("aria-label") ?? e.textContent.trim(),
        })),
    );
    expect(buttons.length).toBeGreaterThan(0);
    for (const b of buttons) {
      expect(b.name, "a named toolbar button").not.toBe("");
      expect(b.height, b.name).toBe(26);
    }
    await expect(bars.first()).not.toContainText(/download/i);
  });

  test(`SHL-08${st}: reduced motion leaves nothing animating`, async ({ page }) => {
    await open(page, st);
    const moving = await page.evaluate(
      () =>
        Array.from(document.querySelectorAll<HTMLElement>("body *"))
          .map((n) => getComputedStyle(n))
          .filter((s) => {
            const seconds = (v: string) =>
              Math.max(...v.split(",").map((p) => parseFloat(p) || 0));
            return (
              (s.animationName !== "none" &&
                s.animationPlayState === "running" &&
                seconds(s.animationDuration) > 0.01) ||
              seconds(s.transitionDuration) > 0.01
            );
          }).length,
    );
    expect(moving).toBe(0);
  });
}

for (const st of DRAWER_STATES) {
  test(`SHL-08${st}: Tier D, the drawer is 480 wide with a 46 px header and 14.5/500 title`, async ({
    page,
  }) => {
    await open(page, st);
    const box = await drawer(page).boundingBox();
    expect(box?.width).toBe(480);
    await expect(drawer(page)).toHaveAttribute("aria-labelledby", /.+/);
    const header = await drawer(page).evaluate((el) => {
      const head = el.querySelector<HTMLElement>("header");
      const title = head?.querySelector<HTMLElement>("h1, h2, h3") ?? null;
      return {
        height: head?.getBoundingClientRect().height ?? 0,
        size: title === null ? "" : getComputedStyle(title).fontSize,
        weight: title === null ? "" : getComputedStyle(title).fontWeight,
      };
    });
    expect(header).toEqual({ height: 46, size: "14.5px", weight: "500" });
  });
}

test("SHL-08b: Tier D, the dock pane is 330 wide", async ({ page }) => {
  await open(page, "b");
  const width = await page.evaluate(() => {
    const viewer = document.querySelector<HTMLElement>("[data-viewer-bar]");
    let node: HTMLElement | null = viewer;
    while (node !== null && Math.round(node.getBoundingClientRect().width) > 330)
      node = node.parentElement;
    while (
      node?.parentElement &&
      Math.round(node.parentElement.getBoundingClientRect().width) === 330
    )
      node = node.parentElement;
    return node === null ? 0 : Math.round(node.getBoundingClientRect().width);
  });
  expect(width).toBe(330);
});

test("SHL-08a: Tier D, linked-figure rows are 36 px", async ({ page }) => {
  await open(page, "a");
  const rows = await page
    .locator(
      "[data-linked-figures] [role='row'], [data-linked-figures] li, [data-linked-figures] tr",
    )
    .evaluateAll((els) => els.map((e) => e.getBoundingClientRect().height));
  expect(rows.length).toBeGreaterThan(0);
  for (const h of rows) expect(h).toBe(36);
});

test("SHL-08a: the toolbar is reachable and operable by keyboard", async ({ page }) => {
  await open(page, "a");
  const first = page.locator("[data-viewer-bar] button").first();
  await first.focus();
  await expect(first).toBeFocused();
  await page.keyboard.press("Tab");
  const inBar = await page.evaluate(
    () => document.activeElement?.closest("[data-viewer-bar], [data-overlay]") !== null,
  );
  expect(inBar).toBe(true);
});

test("SHL-08d: the unlock form is labelled, keyboard-submitted and clears the field", async ({
  page,
}) => {
  await open(page, "d");
  await expect(page.getByText("This PDF is password-protected.")).toBeVisible();
  const field = page.getByLabel("Password");
  await expect(field).toHaveAttribute("type", "password");
  await expect(field).toHaveAttribute("autocomplete", "off");
  await field.focus();
  await page.keyboard.type("not-the-password");
  await page.keyboard.press("Enter");
  const error = page.getByText("That password didn't open the file.");
  await expect(error).toBeVisible();
  await expect(field).toHaveValue("");
  const described = await field.getAttribute("aria-describedby");
  expect(described).toBe(await error.getAttribute("id"));
  expect(await page.content()).not.toContain("not-the-password");
  expect(await serious(page)).toEqual([]);
});

test("SHL-08c: Reveal (logged) is a keyboard-reachable named button", async ({ page }) => {
  await open(page, "c");
  const reveal = page.getByRole("button", { name: /Reveal/ }).first();
  await reveal.focus();
  await expect(reveal).toBeFocused();
  await expect(page.locator("[aria-live='polite']").first()).toBeAttached();
});
