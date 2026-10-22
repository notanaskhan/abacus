// Tier D: exact computed styles of the specimens (F-05-T16; chapter 04 §9.3). Not pixels, so it is
// robust to rasterisation and needs no baseline: it blocks everywhere the gallery runs. Each row is
// a number the kit handoff states (C-06 "Pill sizes", chapter 04's Tier D list) and the live
// element must compute to exactly. The templates' geometry (toolbar 46, subbar 42, audit bar 59,
// pane header 46, nav item 32) joins this table as each template merges.
import { expect, test } from "@playwright/test";
import { openGallery, specimen } from "./support";

type Expected = {
  height: string;
  fontSize: string;
  fontWeight: string;
  paddingLeft: string;
  paddingRight: string;
};

// Pill sizes, from the C-06 handoff sheet "02 Pill sizes": height, padding and type per size. The
// word picks the pill in the "Pill sizes" sheet of /components (`nth` where the word also appears
// on the variants sheet above it).
const PILLS: readonly {
  size: string;
  selector: string;
  expected: Expected;
}[] = [
  {
    size: "state",
    selector: 'span:text-is("In review") >> nth=-1',
    expected: {
      height: "21px",
      fontSize: "12px",
      fontWeight: "500",
      paddingLeft: "8px",
      paddingRight: "8px",
    },
  },
  {
    size: "card-state",
    selector: 'span:text-is("Planning")',
    expected: {
      height: "21px",
      fontSize: "11.5px",
      fontWeight: "500",
      paddingLeft: "9px",
      paddingRight: "9px",
    },
  },
  {
    size: "sm",
    selector: 'span:text-is("Matched") >> nth=-1',
    expected: {
      height: "19px",
      fontSize: "11px",
      fontWeight: "500",
      paddingLeft: "8px",
      paddingRight: "8px",
    },
  },
  {
    size: "micro",
    selector: 'span:text-is("MS")',
    expected: {
      height: "18px",
      fontSize: "10.5px",
      fontWeight: "500",
      paddingLeft: "5px",
      paddingRight: "6px",
    },
  },
  {
    size: "status",
    selector: 'span:text-is("Not started") >> nth=1',
    expected: {
      height: "25px",
      fontSize: "12.5px",
      fontWeight: "500",
      paddingLeft: "13px",
      paddingRight: "11px",
    },
  },
  {
    size: "outline",
    selector: 'span:text-is("Available") >> nth=-1',
    expected: {
      height: "22px",
      fontSize: "11.5px",
      fontWeight: "500",
      paddingLeft: "9px",
      paddingRight: "9px",
    },
  },
  {
    size: "tally",
    selector: 'span:text-is("tie")',
    expected: {
      height: "17px",
      fontSize: "10.5px",
      fontWeight: "500",
      paddingLeft: "6px",
      paddingRight: "6px",
    },
  },
  {
    size: "tag",
    selector: 'span:text-is("Factual") >> nth=-1',
    expected: {
      height: "23px",
      fontSize: "11.5px",
      fontWeight: "500",
      paddingLeft: "9px",
      paddingRight: "9px",
    },
  },
];

test.describe("tier D: computed styles", () => {
  test.beforeEach(async ({ page }) => {
    await openGallery(page);
  });

  for (const { size, selector, expected } of PILLS) {
    test(`pill size ${size}`, async ({ page }) => {
      const style = await specimen(page, "c-06-status-pill", selector).evaluate((el) => {
        const c = getComputedStyle(el);
        return {
          height: c.height,
          fontSize: c.fontSize,
          fontWeight: c.fontWeight,
          paddingLeft: c.paddingLeft,
          paddingRight: c.paddingRight,
          borderRadius: c.borderRadius,
          fontFamily: c.fontFamily,
        };
      });
      expect(style).toMatchObject(expected);
      expect(style.borderRadius, "pills are radius 999").toBe("999px");
      expect(style.fontFamily, "Geist").toMatch(/^Geist\b/);
    });
  }

  test("the page type is Geist 13 at 400", async ({ page }) => {
    const body = await page.evaluate(() => {
      const c = getComputedStyle(document.body);
      return { fontSize: c.fontSize, fontWeight: c.fontWeight, fontFamily: c.fontFamily };
    });
    expect(body).toMatchObject({ fontSize: "13px", fontWeight: "400" });
    expect(body.fontFamily).toMatch(/^Geist\b/);
  });

  test("the page type has the plan's 15.6px line", async ({ page }) => {
    // An open decision (tokens/DECISIONS.md, "body line height"): the body keeps 1.45 until
    // F-05-T05's question is closed. Skipped, not expected to fail: CI's Chromium resolved the
    // line to 15.6px while local runs did not, so an expected failure flaked. Drop this marker
    // when the decision lands.
    test.fixme(true, "open decision: body line height 1.45 against the plan's 15.6px");
    const lineHeight = await page.evaluate(() => getComputedStyle(document.body).lineHeight);
    expect(lineHeight).toBe("15.6px");
  });

  test("a pane (the specimen sheets) has radius 12", async ({ page }) => {
    const radius = await specimen(page, "c-06-status-pill", "section >> nth=0").evaluate(
      (el) => getComputedStyle(el).borderRadius,
    );
    expect(radius).toBe("12px");
  });
});

// The shell's geometry (F-05-T18; chapter 04 §9.3): toolbar 46, record header 42, audit bar 59,
// pane header 46, the close variant's 42 + 50, the tabsbars' 50 / 44 / 60, the nav item 32. And the
// toolbar's width test: at 1440, 1400 and 1280 the DF-39 fallbacks apply in order, and the nav
// never wraps or shrinks its type at any width.
test.describe("tier D: the shell", () => {
  test.beforeEach(async ({ page }) => {
    await openGallery(page);
  });

  const HEIGHTS: readonly { name: string; id: string; selector: string; expected: string }[] = [
    {
      name: "toolbar",
      id: "c-00-toolbar",
      selector: '[data-shell="toolbar"] >> nth=0',
      expected: "46px",
    },
    {
      name: "portal toolbar",
      id: "c-00-portal-toolbar",
      selector: '[data-shell="portal-toolbar"] >> nth=0',
      expected: "46px",
    },
    {
      name: "record header (default)",
      id: "c-00-record-header",
      selector: '[data-variant="default"] >> nth=0',
      expected: "42px",
    },
    {
      name: "record header (audit)",
      id: "c-00-record-header",
      selector: '[data-variant="audit"] >> nth=0',
      expected: "59px",
    },
    {
      name: "record header (close), the line",
      id: "c-00-record-header",
      selector: '[data-variant="close"] [data-row="line"]',
      expected: "42px",
    },
    {
      name: "record header (close), the tabs row",
      id: "c-00-record-header",
      selector: '[data-variant="close"] [data-row="tabs"]',
      expected: "50px",
    },
    {
      name: "record header (settings)",
      id: "c-00-record-header",
      selector: '[data-variant="settings"]',
      expected: "42px",
    },
    {
      name: "pane header",
      id: "c-00-pane",
      selector: '[data-shell="pane-header"] >> nth=0',
      expected: "46px",
    },
    {
      name: "tabsbar (default)",
      id: "c-00-tabsbar",
      selector: '[data-size="default"]',
      expected: "50px",
    },
    {
      name: "tabsbar (compact)",
      id: "c-00-tabsbar",
      selector: '[data-size="compact"]',
      expected: "44px",
    },
    {
      name: "tabsbar (workbench)",
      id: "c-00-tabsbar",
      selector: '[data-size="workbench"]',
      expected: "60px",
    },
  ];

  for (const { name, id, selector, expected } of HEIGHTS) {
    test(`${name} is ${expected}`, async ({ page }) => {
      const height = await specimen(page, id, selector).evaluate(
        (el) => getComputedStyle(el).height,
      );
      expect(height).toBe(expected);
    });
  }

  test("a pane header title is 14.5 / 500 Geist", async ({ page }) => {
    const style = await specimen(
      page,
      "c-00-pane",
      '[data-shell="pane-header"] h2 >> nth=0',
    ).evaluate((el) => {
      const c = getComputedStyle(el);
      return { fontSize: c.fontSize, fontWeight: c.fontWeight, fontFamily: c.fontFamily };
    });
    expect(style).toMatchObject({ fontSize: "14.5px", fontWeight: "500" });
    expect(style.fontFamily).toMatch(/^Geist\b/);
  });

  // The first four strips of the width test, in the specimen's order.
  const WIDTHS = [
    { width: 1440, stage: "none", more: false, home: false },
    { width: 1400, stage: "firm-short", more: false, home: false },
    { width: 1280, stage: "signatures-closes-audits", more: true, home: true },
    { width: 1080, stage: "narrow", more: true, home: true },
  ] as const;

  WIDTHS.forEach(({ width, stage, more, home }, index) => {
    test(`the toolbar at ${String(width)} is at step ${stage}`, async ({ page }) => {
      const bar = specimen(page, "c-00-toolbar", `[data-shell="toolbar"] >> nth=${String(index)}`);
      const facts = await bar.evaluate((el) => {
        const nav = el.querySelector("nav");
        const items = [...(nav?.querySelectorAll("button") ?? [])];
        return {
          width: el.getBoundingClientRect().width,
          stage: el.getAttribute("data-stage"),
          more: items.some((b) => b.textContent === "More"),
          home: el.querySelector('button[aria-label="Home"]') !== null,
          labels: items.map((b) => b.textContent),
          navClips: nav === null ? true : nav.scrollWidth > nav.clientWidth,
          itemStyles: items.map((b) => {
            const c = getComputedStyle(b);
            return { fontSize: c.fontSize, height: c.height, whiteSpace: c.whiteSpace };
          }),
        };
      });
      expect(facts.width).toBe(width);
      expect(facts.stage).toBe(stage);
      expect(facts.more).toBe(more);
      expect(facts.home).toBe(home);
      expect(facts.navClips, "the nav never overflows its space").toBe(false);
      for (const style of facts.itemStyles) {
        expect(style, "13.5px, 32 high, on one line, whatever the width").toEqual({
          fontSize: "13.5px",
          height: "32px",
          whiteSpace: "nowrap",
        });
      }
      // What is hidden is a trailing run of the nav order, never a gap.
      if (stage === "signatures-closes-audits") {
        const shown = facts.labels;
        for (const hidden of ["Signatures", "Closes", "Audits"])
          expect(shown).not.toContain(hidden);
        expect(shown).toContain("Notices");
      }
    });
  });
});

// SHL-01 (P-01-T02; P-01 §5.4): the app's toolbar on its fixture artboard, blocking. Toolbar 46,
// nav item 32, pills 30, bell 30 x 30, dot 6 px, Geist 13.5 (400, 500 on the lit item); and the
// 1400 strips of frame b at DF-39's More-first step: Signatures in More, the full firm name, Home
// in the nav.
test.describe("tier D: SHL-01 toolbar", () => {
  const box = (el: Element, sel: string) => {
    const target = sel === "" ? el : el.querySelector(sel);
    if (target === null) return null;
    const c = getComputedStyle(target);
    return {
      width: c.width,
      height: c.height,
      fontSize: c.fontSize,
      fontWeight: c.fontWeight,
      fontFamily: c.fontFamily,
    };
  };

  test("frame a: toolbar 46, nav item 32, pills 30, bell 30 x 30, dot 6, Geist 13.5", async ({
    page,
  }) => {
    await openGallery(page, "screens/SHL-01?st=a");
    const bar = page.locator('[data-artboard="a"] [data-shell="toolbar"]');
    await expect(bar.getByRole("button", { name: "Notifications, unread" })).toBeVisible();
    expect((await bar.evaluate(box, ""))?.height).toBe("46px");
    const item = await bar.evaluate(box, 'nav button[aria-current="page"]');
    expect(item).toMatchObject({ height: "32px", fontSize: "13.5px", fontWeight: "500" });
    expect(item?.fontFamily).toMatch(/^Geist\b/);
    const idle = await bar.evaluate(box, "nav button:not([aria-current])");
    expect(idle).toMatchObject({ height: "32px", fontSize: "13.5px", fontWeight: "400" });
    for (const name of ["Go to anything ⌘K", "Brightwater Hale", "Support"]) {
      const pill = await bar
        .getByRole("button", { name, exact: true })
        .evaluate((el) => getComputedStyle(el).height);
      expect(pill, name).toBe("30px");
    }
    const bell = await bar
      .getByRole("button", { name: "Notifications, unread" })
      .evaluate((el) => ({ w: getComputedStyle(el).width, h: getComputedStyle(el).height }));
    expect(bell).toEqual({ w: "30px", h: "30px" });
    const dot = await bar.evaluate(box, '[data-dot="unread"]');
    expect(dot).toMatchObject({ width: "6px", height: "6px" });
  });

  test("frame b: thirteen 1400 strips, Signatures in More, the full firm name", async ({
    page,
  }) => {
    await openGallery(page, "screens/SHL-01?st=b");
    const bars = page.locator('[data-artboard="b"] [data-shell="toolbar"]');
    await expect(bars).toHaveCount(13);
    for (let i = 0; i < 13; i++) {
      const facts = await bars.nth(i).evaluate((el) => ({
        width: el.getBoundingClientRect().width,
        stage: el.getAttribute("data-stage"),
        firm: el.querySelector('button[aria-haspopup="menu"]')?.textContent ?? "",
      }));
      expect(facts).toEqual({ width: 1400, stage: "signatures", firm: "Brightwater Hale" });
    }
  });
});
