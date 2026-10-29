// AUD-06 a–h and POR-16 a–g in fixture mode (A-02-T31; A-02 §10 DoD): every artboard and its open
// overlay from the /components gallery on fixtures, with axe at zero serious or critical findings
// and a keyboard path (Tab from the top of the artboard reaches a control with a visible focus
// ring); the segmented suite (AUD-06's Audit area and Layer tablists: arrows move the selection,
// disabled options are skipped), the grid suite (Tab reaches the lines table's formula cells) and
// the toggle suite (POR-16's authorisation switch: Space flips it, the label names it). POR-16
// also stays white-labelled and read-only (DF-19): no "Accrued", no posting copy. Tier C parity is
// reported by e2e/parity/screens.spec.ts (`aud-06x.window`, `por-16x.window`) and the hosts'
// geometry by e2e/visual/tier-d-connections.spec.ts.
// Run: `ABACUS_VISUAL=1 pnpm exec playwright test --project=chromium e2e/screens/AUD-06-POR-16.spec.ts`.
import AxeBuilder from "@axe-core/playwright";
import { type Locator, type Page, expect, test } from "@playwright/test";

const SERIOUS = new Set(["serious", "critical"]);
const SCREENS = { "AUD-06": "abcdefgh", "POR-16": "abcdefg" } as const;
const TAB_LIMIT = 40;
const PORTAL_WORDS = /Accrued|post (?:approved|accepted)? ?entries|Post approved entries/i;

test.use({
  viewport: { width: 1440, height: 900 },
  deviceScaleFactor: 2,
  reducedMotion: "reduce",
});

async function open(page: Page, screen: string, st: string): Promise<Locator> {
  await page.goto(`/components/screens/${screen}?st=${st}&frame=1&static=1`);
  const board = page.locator(`[data-artboard='${st}']`);
  await expect(board).toBeVisible();
  await expect(board.locator("[data-shell='app']").first()).toBeVisible();
  return board;
}

async function seriousFindings(page: Page, st: string): Promise<string[]> {
  // An open sheet or dialog is portalled out of the artboard: axe runs on it as well.
  const { violations } = await new AxeBuilder({ page })
    .include(`[data-artboard='${st}']`)
    .include("[role='dialog']")
    .include("[role='alertdialog']")
    .analyze();
  return violations
    .filter((v) => SERIOUS.has(v.impact ?? ""))
    .map((v) => `${v.id}: ${v.help} — ${v.nodes[0]?.target.join(" ") ?? ""}`);
}

for (const [screen, states] of Object.entries(SCREENS)) {
  for (const st of states) {
    test(`${screen}${st}: renders, axe finds nothing serious, the keyboard reaches a control`, async ({
      page,
    }) => {
      const board = await open(page, screen, st);
      expect(await seriousFindings(page, st)).toEqual([]);
      if (screen === "POR-16") {
        const text = await page.locator("body").innerText();
        expect(text).not.toMatch(PORTAL_WORDS);
      }

      await board
        .locator("[data-shell='app']")
        .first()
        .evaluate((shell: HTMLElement) => {
          shell.tabIndex = -1;
          shell.focus();
        });
      let reached = false;
      for (let i = 0; i < TAB_LIMIT && !reached; i += 1) {
        await page.keyboard.press("Tab");
        // An artboard that opens on a sheet or dialog (POR-16 b, e, f) traps focus there.
        reached = await board.evaluate((board) => {
          const modal = document.querySelector("[role='dialog'], [role='alertdialog']");
          const root = modal ?? board;
          const active = document.activeElement;
          if (active === null || !root.contains(active)) return false;
          const style = getComputedStyle(active);
          const ring = style.outlineStyle !== "none" || style.boxShadow !== "none";
          const control =
            "a[href], button, [role='row'], [role='tab'], [role='switch'], input, textarea, [tabindex='0']";
          return active.matches(control) && ring;
        });
      }
      expect(reached, `${screen}${st}: Tab reaches a focusable control with a ring`).toBe(true);
    });
  }
}

test("AUD-06a segmented: arrows move the Audit area selection and skip disabled options", async ({
  page,
}) => {
  const board = await open(page, "AUD-06", "a");
  const list = board.getByRole("tablist", { name: "Audit area" });
  const selected = list.locator("[role='tab'][aria-selected='true']");
  const before = await selected.innerText();
  await selected.focus();
  await page.keyboard.press("ArrowRight");
  const focused = page.locator(":focus");
  await expect(focused).toHaveAttribute("role", "tab");
  expect(await focused.getAttribute("aria-disabled")).not.toBe("true");
  expect(await focused.isDisabled()).toBe(false);
  expect(await focused.innerText()).not.toBe(before);
  // Roving tabindex: one tab of the list is in the Tab order.
  expect(await list.locator("[role='tab'][tabindex='0']").count()).toBe(1);
});

test("AUD-06a grid: Tab reaches a formula cell in the lines table", async ({ page }) => {
  const board = await open(page, "AUD-06", "a");
  const cells = board.locator("[data-aud06='lines'] [tabindex='0']");
  expect(await cells.count()).toBeGreaterThan(0);
  await board.locator("[data-aud06='lines']").evaluate((table: HTMLElement) => {
    table.tabIndex = -1;
    table.focus();
  });
  await page.keyboard.press("Tab");
  const inTable = await page.evaluate(() => {
    const active = document.activeElement;
    return active?.closest("[data-aud06='lines']") !== null;
  });
  expect(inTable).toBe(true);
});

test("POR-16e toggle: the authorisation switch is named, Space flips it", async ({ page }) => {
  await open(page, "POR-16", "e");
  const toggle = page.getByRole("switch").first();
  await expect(toggle).toBeVisible();
  expect((await toggle.getAttribute("aria-label")) ?? (await toggle.innerText())).not.toBe("");
  const before = await toggle.getAttribute("aria-checked");
  await toggle.focus();
  await page.keyboard.press("Space");
  await expect(toggle).not.toHaveAttribute("aria-checked", before ?? "false");
});
