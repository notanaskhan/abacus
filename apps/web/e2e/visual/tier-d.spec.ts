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
      name: "portal mobile header (T7-M)",
      id: "t7-portal-layout",
      selector: '[data-shell="mobile-header"] >> nth=0',
      expected: "56px",
    },
    {
      name: "portal bottom tab bar (T7-M)",
      id: "t7-portal-layout",
      selector: '[data-shell="mobile-tab-bar"] >> nth=0',
      expected: "64px",
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

// T15 AuthCard (F-05-T37): the 400 card (radius 14, padding 28 28 24), the 44 × 52 code boxes, the
// 720 page; and TPL-15e and TPL-15j at 390 with no horizontal scroll.
test.describe("tier D: T15 auth card", () => {
  test.beforeEach(async ({ page }) => {
    await openGallery(page);
  });

  test("the card is 400 wide, radius 14, padding 28 28 24; code boxes 44 x 52", async ({
    page,
  }) => {
    const card = await specimen(
      page,
      "tpl-15",
      '[data-artboard="tpl-15b"] [data-auth="card"]',
    ).evaluate((el) => {
      const c = getComputedStyle(el);
      return {
        width: c.width,
        radius: c.borderRadius,
        padding: [c.paddingTop, c.paddingRight, c.paddingBottom, c.paddingLeft].join(" "),
      };
    });
    expect(card).toEqual({ width: "400px", radius: "14px", padding: "28px 28px 24px 28px" });
    const box = await specimen(
      page,
      "tpl-15",
      '[data-artboard="tpl-15b"] [data-auth="code"] input',
    )
      .first()
      .evaluate((el) => ({ w: getComputedStyle(el).width, h: getComputedStyle(el).height }));
    expect(box).toEqual({ w: "44px", h: "52px" });
    const paper = await specimen(
      page,
      "tpl-15",
      '[data-artboard="tpl-15f"] [data-auth="page"]',
    ).evaluate((el) => getComputedStyle(el).width);
    expect(paper).toBe("720px");
  });

  for (const id of ["tpl-15e", "tpl-15j"]) {
    test(`${id} renders at 390 with no horizontal scroll`, async ({ page }) => {
      const facts = await specimen(
        page,
        "tpl-15",
        `[data-artboard="${id}"] [data-variant="auth-mobile"]`,
      ).evaluate((el) => {
        const body = el.querySelector("main") as HTMLElement;
        return {
          width: el.getBoundingClientRect().width,
          overflow: body.scrollWidth - body.clientWidth,
        };
      });
      expect(facts).toEqual({ width: 390, overflow: 0 });
    });
  }
});

// T2 RecordCockpit (F-05-T40): the rail and the dock are 330, the canvas 696 beside the dock and
// 1036 without it (to x1388 in the 1400 window), under the 59 audit bar; the layout chip toggles it.
test.describe("tier D: T2 record cockpit", () => {
  test.beforeEach(async ({ page }) => {
    await openGallery(page);
  });

  const widths = (el: Element) => {
    const w = (sel: string): number | null => {
      const node = el.querySelector(sel);
      return node === null ? null : node.getBoundingClientRect().width;
    };
    return {
      rail: w('[data-cockpit="rail"]'),
      canvas: w('[data-cockpit="canvas"]'),
      dock: w('[data-cockpit="dock"]'),
      bar: el.querySelector('[data-variant="audit"]')?.getBoundingClientRect().height ?? null,
    };
  };

  test("T2a: rail 330, canvas 696, dock 330, audit bar 59", async ({ page }) => {
    const facts = await specimen(page, "t2-record-cockpit", '[data-artboard="t2a"]').evaluate(
      widths,
    );
    expect(facts).toEqual({ rail: 330, canvas: 696, dock: 330, bar: 59 });
  });

  test("T2e: no dock, the canvas runs to 1036; the layout chip brings the dock back", async ({
    page,
  }) => {
    const board = specimen(page, "t2-record-cockpit", '[data-artboard="t2e"]');
    expect(await board.evaluate(widths)).toEqual({ rail: 330, canvas: 1036, dock: null, bar: 59 });
    await board.getByRole("button", { name: "Layout" }).click();
    expect(await board.evaluate(widths)).toEqual({ rail: 330, canvas: 696, dock: 330, bar: 59 });
  });
});

// T3 EvidenceTriad (F-05-T53): toolbar 46, record subbar 42, tabsbar 44, and the three presets'
// panes, 706 tall: Review 452 · 452 · 452, Prepare 214 · 571 · 571, two-pane sheet flex · 490.
test.describe("tier D: T3 evidence triad", () => {
  test.beforeEach(async ({ page }) => {
    await openGallery(page);
  });

  const facts = (el: Element) => {
    const w = (sel: string): number | null => {
      const node = el.querySelector(sel);
      return node === null ? null : Math.round(node.getBoundingClientRect().width);
    };
    const h = (sel: string): number | null => {
      const node = el.querySelector(sel);
      return node === null ? null : Math.round(node.getBoundingClientRect().height);
    };
    return {
      tree: w('[data-triad-pane="tree"]'),
      viewer: w('[data-triad-pane="viewer"]'),
      sheet: w('[data-triad-pane="sheet"]'),
      height: h('[data-shell="pane"]'),
      subbar: h('[data-shell="record-header"]'),
      tabsbar: h('[data-shell="tabsbar"]'),
    };
  };

  for (const [id, expected] of [
    ["t3a", { tree: 214, viewer: 571, sheet: 571 }],
    ["t3b", { tree: 452, viewer: 452, sheet: 452 }],
    ["t3d", { tree: null, viewer: 490, sheet: 876 }],
  ] as const) {
    test(`${id}: panes ${JSON.stringify(expected)}, 706 tall, subbar 42, tabsbar 44`, async ({
      page,
    }) => {
      const got = await specimen(page, "t3-evidence-triad", `[data-artboard="${id}"]`).evaluate(
        facts,
      );
      expect(got).toEqual({ ...expected, height: 706, subbar: 42, tabsbar: 44 });
    });
  }
});

// T8 InboxLayout (F-05-T56): filter bar 50 (−10), rail 392 beside the reading pane, panes 752 tall;
// rail rows at least 52.
test.describe("tier D: T8 inbox master-detail", () => {
  test.beforeEach(async ({ page }) => {
    await openGallery(page);
  });

  test("t8a: rail 392, panes 752 tall, rows ≥ 52", async ({ page }) => {
    const got = await specimen(page, "t8-inbox", '[data-artboard="t8a"]').evaluate((el) => {
      const first = el.querySelector("[data-split-pane]");
      const rows = [...el.querySelectorAll("[data-inbox-row]")].map((r) =>
        Math.round(r.getBoundingClientRect().height),
      );
      return {
        rail: first === null ? null : Math.round(first.getBoundingClientRect().width),
        height: first === null ? null : Math.round(first.getBoundingClientRect().height),
        shortRows: rows.filter((h) => h < 52).length,
      };
    });
    expect(got).toEqual({ rail: 392, height: 752, shortRows: 0 });
  });
});

// T9 QueueDetailLayout (F-05-T55): the three presets' panes. Individual 546 · 433 · 377 (706
// tall, queue card 262), close-review 790 · 576 (700 tall, queue 310), entity 470 · 896 (700 tall).
test.describe("tier D: T9 queue · detail · evidence", () => {
  test.beforeEach(async ({ page }) => {
    await openGallery(page);
  });

  for (const [id, expected] of [
    ["t9a", { panes: [546, 433, 377], height: 706, queue: 262 }],
    ["t9b", { panes: [790, 576], height: 700, queue: 310 }],
    ["t9c", { panes: [470, 896], height: 700, queue: 470 }],
  ] as const) {
    test(`${id}: panes ${JSON.stringify(expected)}`, async ({ page }) => {
      const got = await specimen(page, "t9-queue-detail", `[data-artboard="${id}"]`).evaluate(
        (el) => {
          const panes = [...el.querySelectorAll("[data-split-pane]")].map((p) =>
            Math.round(p.getBoundingClientRect().width),
          );
          const first = el.querySelector("[data-split-pane]");
          const queue = el.querySelector('[data-queue-part="queue"]');
          return {
            panes,
            height: first === null ? null : Math.round(first.getBoundingClientRect().height),
            queue: queue === null ? null : Math.round(queue.getBoundingClientRect().width),
          };
        },
      );
      expect(got).toEqual(expected);
    });
  }
});

// TPL-03 (F-05-T54): the Feld 1040 review at 452 × 3 (a, c, d, e) and 214 · 571 · 571 (b), with
// the K-1 matrix rows 41 tall.
test.describe("tier D: TPL-03 Feld 1040 review", () => {
  test.beforeEach(async ({ page }) => {
    await openGallery(page);
  });

  for (const [id, expected] of [
    ["tpl-03a", { tree: 452, viewer: 452, sheet: 452 }],
    ["tpl-03b", { tree: 214, viewer: 571, sheet: 571 }],
  ] as const) {
    test(`${id}: panes ${JSON.stringify(expected)}`, async ({ page }) => {
      const got = await specimen(page, "tpl-03", `[data-artboard="${id}"]`).evaluate((el) => {
        const w = (sel: string): number | null => {
          const node = el.querySelector(sel);
          return node === null ? null : Math.round(node.getBoundingClientRect().width);
        };
        return {
          tree: w('[data-triad-pane="tree"]'),
          viewer: w('[data-triad-pane="viewer"]'),
          sheet: w('[data-triad-pane="sheet"]'),
        };
      });
      expect(got).toEqual(expected);
    });
  }

  test("tpl-03a: K-1 matrix rows are 41 tall", async ({ page }) => {
    const h = await specimen(
      page,
      "tpl-03",
      '[data-artboard="tpl-03a"] [data-k1-row="type"]',
    ).evaluate((el) => Math.round(el.getBoundingClientRect().height));
    expect(h).toBe(41);
  });
});

// The M5 lock (F-05-T49): T11 DashboardLayout, T12 SettingsLayout and the O6 wizard, at the numbers
// their canvases state (Wave 0 - Foundations `#t11`, `#t12`; Wave 0 - Templates TPL-11, TPL-12,
// TPL-18). Box sizes are measured inside the 1400 window, so they hold at any page offset.
test.describe("tier D: T11, T12 and O6 (M5 lock)", () => {
  test.beforeEach(async ({ page }) => {
    await openGallery(page);
  });

  test("TPL-11a: tiles row 109, tiles 120 x 99, KPI 22px, column 420, deadlines 360", async ({
    page,
  }) => {
    const facts = await specimen(
      page,
      "tpl-11",
      '[data-artboard="tpl-11a"] [data-shell="app"]',
    ).evaluate((win) => {
      const tile = win.querySelector('[data-tile="single"]')?.getBoundingClientRect();
      const kpi = win.querySelector('[data-tile="single"] > span');
      const panes = [...win.querySelectorAll('[data-shell="cols"] [data-shell="pane"]')].map((p) =>
        p.getBoundingClientRect(),
      );
      return {
        tilesRow: win.querySelector('[data-dashboard="tiles"]')?.getBoundingClientRect().height,
        tile: tile === undefined ? null : [tile.width, tile.height],
        kpi: kpi === null ? null : getComputedStyle(kpi).fontSize,
        column: panes[1]?.width,
        deadlines: panes[1]?.height,
        paneHeader: win.querySelector('[data-shell="pane-header"]')?.getBoundingClientRect()
          .height,
      };
    });
    expect(facts).toEqual({
      tilesRow: 109,
      tile: [120, 99],
      kpi: "22px",
      column: 420,
      deadlines: 360,
      paneHeader: 46,
    });
  });

  test("T11a: the deadlines pane is 334 and the queue rows 52", async ({ page }) => {
    const facts = await specimen(page, "t11-dashboard", '[data-artboard="t11a"]').evaluate(
      (b) => ({
        deadlines: b
          .querySelectorAll('[data-shell="cols"] [data-shell="pane"]')[1]
          ?.getBoundingClientRect().height,
        row: b.querySelector("a[data-queue-row]")?.getBoundingClientRect().height,
      }),
    );
    expect(facts).toEqual({ deadlines: 334, row: 52 });
  });

  test("TPL-12a: settings bar 42, section list 240, nav rows 33, value rows 34, fieldsets 760", async ({
    page,
  }) => {
    const facts = await specimen(
      page,
      "tpl-12",
      '[data-artboard="tpl-12a"] [data-shell="app"]',
    ).evaluate((win) => {
      const panes = [...win.querySelectorAll('[data-shell="cols"] [data-shell="pane"]')];
      const fieldset = win.querySelector('[data-settings="form"] section');
      return {
        bar: win.querySelector('[data-variant="settings"]')?.getBoundingClientRect().height,
        list: panes[0]?.getBoundingClientRect().width,
        navRow: win.querySelector('nav[aria-label="Sections"] button')?.getBoundingClientRect()
          .height,
        valueRow: fieldset?.querySelector("label")?.parentElement?.getBoundingClientRect().height,
        fieldset: fieldset?.getBoundingClientRect().width,
      };
    });
    expect(facts).toEqual({ bar: 42, list: 240, navRow: 33, valueRow: 34, fieldset: 760 });
  });

  test("TPL-18a: the O6 sheet is inset 14 from top 60, radius 14; list 220, header 46, footer 56, steps 38", async ({
    page,
  }) => {
    const facts = await specimen(
      page,
      "tpl-18",
      '[data-artboard="tpl-18a"] [data-shell="app"]',
    ).evaluate((win) => {
      const w = win.getBoundingClientRect();
      const sheet = win.querySelector('[role="group"][aria-label="New engagement"]');
      const s = sheet?.getBoundingClientRect();
      return {
        left: s === undefined ? null : s.left - w.left,
        top: s === undefined ? null : s.top - w.top,
        right: s === undefined ? null : w.right - s.right,
        bottom: s === undefined ? null : w.bottom - s.bottom,
        radius: sheet === null ? null : getComputedStyle(sheet).borderTopLeftRadius,
        list: sheet?.querySelector('nav[aria-label="Steps"]')?.getBoundingClientRect().width,
        header: sheet?.querySelector("header")?.getBoundingClientRect().height,
        footer: sheet?.querySelector("footer")?.getBoundingClientRect().height,
        step: sheet?.querySelector('[aria-current="step"]')?.getBoundingClientRect().height,
      };
    });
    expect(facts).toEqual({
      left: 14,
      top: 60,
      right: 14,
      bottom: 14,
      radius: "14px",
      list: 220,
      header: 46,
      footer: 56,
      step: 38,
    });
  });
});
