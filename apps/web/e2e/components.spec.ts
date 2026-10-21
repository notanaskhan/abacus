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

// F-05-T15 (Component Sheet F, C-05): the inputs and tabs in a real browser. A control under 24px
// keeps a 24px hit area, which jsdom cannot lay out; Segmented wraps with the arrow keys; a menu
// opens with the arrow and returns focus on Escape; a tooltip opens on keyboard focus.
test.describe("inputs and tabs", () => {
  test("hit areas: a pointer just past a small control's box still lands on it", async ({
    page,
  }) => {
    await page.goto("/components");
    await expect(page.locator("#f-checkbox")).toBeVisible();
    const result = await page.evaluate(() => {
      // [selector, accessible name, offset of the probe from the control's centre in px]
      const probes: [string, string, number, number][] = [
        ["#f-checkbox [role=checkbox]", "Off", -(15 / 2 + 4), 0],
        ["#f-radio [role=radio]", "Off", 17 / 2 + 3, 0],
        ["#f-radio [role=radio]", "Open issue", 0, -(13 / 2 + 5)],
        ["#f-toggle [role=switch]", "Off 38 × 22", 0, 11 + 0.5],
        ["#f-toggle [role=switch]", "Off 34 × 20", 0, 10 + 1.5],
      ];
      return probes.map(([selector, name, dx, dy]) => {
        const el = [...document.querySelectorAll(selector)].find(
          (e) => e.getAttribute("aria-label") === name,
        );
        if (el === undefined) return `${name}: missing`;
        el.scrollIntoView({ block: "center" });
        const r = el.getBoundingClientRect();
        const hit = document.elementFromPoint(
          r.left + r.width / 2 + dx,
          r.top + r.height / 2 + dy,
        );
        return hit === el ? "hit" : `${name}: missed`;
      });
    });
    expect(result).toEqual(["hit", "hit", "hit", "hit", "hit"]);
  });

  test("Segmented wraps with the arrow keys", async ({ page }) => {
    await page.goto("/components");
    const tabs = page.locator('#c-05-segmented [role=tablist][aria-label="Workbench"]');
    await tabs.getByRole("tab", { name: "Sessions" }).focus();
    await page.keyboard.press("ArrowLeft");
    await expect(tabs.getByRole("tab", { name: "Connect" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    await expect(tabs.getByRole("tab", { name: "Connect" })).toBeFocused();
    await page.keyboard.press("ArrowRight");
    await expect(tabs.getByRole("tab", { name: "Sessions" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
  });

  test("ViewToggle opens with ArrowDown, and Escape returns focus to the button", async ({
    page,
  }) => {
    await page.goto("/components");
    const toggle = page
      .locator("#c-05-view-toggle")
      .getByRole("button", { name: "View: Grid" })
      .first();
    await toggle.focus();
    await page.keyboard.press("ArrowDown");
    await expect(page.getByRole("menuitemradio", { name: "Grid" })).toBeFocused();
    await page.keyboard.press("Escape");
    await expect(toggle).toBeFocused();
  });

  test("a tooltip opens on keyboard focus", async ({ page }) => {
    await page.goto("/components");
    await page.locator("#c-00-tooltip").getByRole("button", { name: "Prepared" }).first().focus();
    await page.keyboard.press("Shift+Tab");
    await page.keyboard.press("Tab");
    await expect(page.getByRole("tooltip").first()).toContainText("Prepared by Sam Staff");
  });
});

// F-05-T19 (C-20): a pane keeps its frame in every mode. The header, the table head and the rows
// are measured in a real layout, which jsdom cannot do: Loaded, Loading, Empty and Error of the
// Files pane, and the Sessions pane, have the same pane, header and row heights.
test.describe("view states", () => {
  const MODES = ["Loaded", "Loading", "Empty", "Error"] as const;

  for (const [kind, row, rowHeight] of [
    ["files", "table", 40],
    ["sessions", "list", 48],
  ] as const) {
    test(`c-20: the ${kind} pane keeps its header and row heights in every mode`, async ({
      page,
    }) => {
      await page.goto("/components");
      const pane = page.locator(`#c-20-view-states [data-pane="${kind}"]`);
      await pane.scrollIntoViewIfNeeded();
      const frame = async (): Promise<{
        pane: number;
        header: number;
        head: number | null;
        rows: number[];
      }> =>
        pane.evaluate((el, rowName) => {
          const h = (e: Element | null): number =>
            e === null ? 0 : e.getBoundingClientRect().height;
          const head = el.querySelector("[data-row='table-head']");
          return {
            pane: h(el),
            header: h(el.querySelector("[data-pane-header]")),
            head: head === null ? null : h(head),
            rows: [...el.querySelectorAll(`[data-row='${rowName}']`)].map(h),
          };
        }, row);
      const loaded = await frame();
      expect(loaded.header).toBe(46);
      if (kind === "files") expect(loaded.head).toBe(30);
      expect(loaded.rows.length).toBeGreaterThan(0);
      for (const height of loaded.rows) expect(height).toBeGreaterThanOrEqual(rowHeight);
      for (const mode of MODES) {
        await pane.getByRole("tab", { name: mode }).click();
        // The skeleton is drawn after 200ms; wait it out so its rows are measured.
        await page.waitForTimeout(350);
        const now = await frame();
        expect(now.pane, mode).toBe(loaded.pane);
        expect(now.header, mode).toBe(46);
        expect(now.head, mode).toBe(loaded.head);
        if (mode === "Loading") {
          for (const height of now.rows) expect(height, mode).toBeGreaterThanOrEqual(rowHeight);
          expect(now.rows.length).toBe(6);
        }
        if (mode === "Empty" || mode === "Error") expect(now.rows).toEqual([]);
      }
    });
  }

  test("c-20: a restricted pane shows no record data, and flag-off is a designed state", async ({
    page,
  }) => {
    await page.goto("/components");
    await expect(page.locator("#c-20-restricted [data-restricted]")).toHaveCount(8);
    await expect(page.locator("#c-20-flag-off")).toContainText(
      "Insights is not turned on for this firm.",
    );
    await expect(page.locator("#c-20-flag-off [data-flag-off]").first()).not.toContainText(
      /404|not found/i,
    );
  });
});
