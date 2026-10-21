// F-05-T18: the toolbar's nav overflow. The widths are what Geist measures on the bar (the 13 nav
// items at weight 500, the controls at their natural size), so the cases are the real ones: all
// 13 fit at 1440, the short firm name is enough at 1400, and 1280 needs Signatures, Closes and
// Audits in More. DF-39's order is a property of the ladder: as the bar narrows the steps come in
// the same order and never skip back.
import { describe, expect, it } from "vitest";
import {
  FALLBACK_STAGES,
  NAV_GAP,
  type ToolbarMeasure,
  fitNav,
  fitToolbar,
  navSpace,
} from "./nav-overflow";

const ITEMS = [
  60.64, 110.23, 98.42, 53.42, 93.75, 95.16, 58.92, 67.73, 71.83, 72.05, 63.92, 66.61, 91.7,
] as const;

function measure(barWidth: number): ToolbarMeasure {
  return {
    barWidth,
    go: 67.84,
    firm: 140.58,
    firmShort: 109.64,
    homePill: 30,
    support: 92.08,
    bell: 30,
    items: ITEMS,
    more: 69.98,
  };
}

const stageIndex = (width: number): number =>
  FALLBACK_STAGES.indexOf(fitToolbar(measure(width)).stage);

describe("fitNav (the bundle's fit)", () => {
  it("keeps every item when they fit, and none move into More", () => {
    expect(fitNav({ itemWidths: [60, 60, 60], moreWidth: 70, navWidth: 300 })).toBe(3);
  });

  it("keeps the leading items that fit beside the More pill", () => {
    // The three need 222; 70 (More) + 61 + 61 = 192 fits in 200 - 2, a third item would make 293.
    expect(fitNav({ itemWidths: [60, 60, 100], moreWidth: 70, navWidth: 200 })).toBe(2);
  });

  it("keeps all with overflow none, whatever the space", () => {
    expect(
      fitNav({ itemWidths: [60, 60, 60], moreWidth: 70, navWidth: 10, overflow: "none" }),
    ).toBe(3);
  });

  it("takes one px of safety each side", () => {
    const total = 60 * 3 + 2 * NAV_GAP;
    expect(fitNav({ itemWidths: [60, 60, 60], moreWidth: 70, navWidth: total + 2 })).toBe(3);
    expect(fitNav({ itemWidths: [60, 60, 60], moreWidth: 70, navWidth: total + 1 })).toBe(1);
  });
});

describe("the DF-39 ladder", () => {
  it("shows all 13 at 1440 and 1500 with nothing given up", () => {
    for (const width of [1500, 1440]) {
      expect(fitToolbar(measure(width))).toEqual({
        stage: "none",
        firmShort: false,
        homePill: false,
        inline: 13,
      });
    }
  });

  it("step 1 at 1400: the firm pill reads Brightwater and all 13 still show", () => {
    expect(fitToolbar(measure(1400))).toEqual({
      stage: "firm-short",
      firmShort: true,
      homePill: false,
      inline: 13,
    });
  });

  it("step 2: Home becomes the house pill, still all 13", () => {
    expect(fitToolbar(measure(1360))).toEqual({
      stage: "home-pill",
      firmShort: true,
      homePill: true,
      inline: 13,
    });
  });

  it("step 3: Signatures moves into More", () => {
    const fit = fitToolbar(measure(1340));
    expect(fit).toMatchObject({
      stage: "signatures",
      homePill: true,
      firmShort: true,
      inline: 12,
    });
  });

  it("step 4 at 1280: Signatures, Closes and Audits move into More", () => {
    const fit = fitToolbar(measure(1280));
    expect(fit).toMatchObject({
      stage: "signatures-closes-audits",
      homePill: true,
      firmShort: true,
      inline: 10,
    });
  });

  it("below that, trailing items leave one at a time and Home is always reachable", () => {
    const fit = fitToolbar(measure(1080));
    expect(fit.stage).toBe("narrow");
    expect(fit.homePill).toBe(true);
    expect(fit.inline).toBeGreaterThanOrEqual(1);
    expect(fit.inline).toBeLessThan(10);
  });

  it("changes step at the widths the measured items give (the numbers in DECISIONS.md)", () => {
    const at = (width: number): string => fitToolbar(measure(width)).stage;
    expect([at(1405), at(1404)]).toEqual(["none", "firm-short"]);
    expect([at(1374), at(1373)]).toEqual(["firm-short", "home-pill"]);
    expect([at(1351), at(1350)]).toEqual(["home-pill", "signatures"]);
    expect([at(1329), at(1328)]).toEqual(["signatures", "signatures-closes-audits"]);
    expect([at(1197), at(1196)]).toEqual(["signatures-closes-audits", "narrow"]);
  });

  it("applies the steps in one order as the bar narrows, and never skips back", () => {
    let previous = 0;
    for (let width = 1700; width >= 700; width -= 4) {
      const now = stageIndex(width);
      expect(now, `at ${String(width)}`).toBeGreaterThanOrEqual(previous);
      previous = now;
    }
    expect(previous).toBe(FALLBACK_STAGES.indexOf("narrow"));
  });

  it("visits every step on the way down", () => {
    const seen = new Set<string>();
    for (let width = 1700; width >= 700; width -= 2) seen.add(fitToolbar(measure(width)).stage);
    expect([...seen]).toEqual([...FALLBACK_STAGES]);
  });

  it("only ever hides a trailing run of the nav, so More lists items in nav order", () => {
    for (let width = 1700; width >= 700; width -= 10) {
      const fit = fitToolbar(measure(width));
      expect(fit.inline).toBeLessThanOrEqual(ITEMS.length);
      expect(fit.inline).toBeGreaterThanOrEqual(1);
    }
  });

  it("chooses the first step at which the nav fits its space", () => {
    for (const width of [1440, 1400, 1360, 1340, 1280]) {
      const m = measure(width);
      const fit = fitToolbar(m);
      const from = fit.homePill ? 1 : 0;
      const shown = ITEMS.slice(from, fit.inline);
      const more = fit.inline < ITEMS.length;
      const needs =
        shown.reduce((a, b) => a + b, 0) +
        (shown.length - 1) * NAV_GAP +
        (more ? NAV_GAP + m.more : 0);
      expect(needs, `at ${String(width)}`).toBeLessThanOrEqual(navSpace(m, fit));
    }
  });

  it("holds a step with `min` (the strips that draw fallback 1 or 2 on purpose)", () => {
    expect(fitToolbar(measure(1500), { min: "firm-short" }).stage).toBe("firm-short");
    expect(fitToolbar(measure(1500), { min: "home-pill" })).toMatchObject({
      stage: "home-pill",
      homePill: true,
      inline: 13,
    });
    // A held step never goes back: at 1280 the fit is already past it.
    expect(fitToolbar(measure(1280), { min: "firm-short" }).stage).toBe(
      "signatures-closes-audits",
    );
  });

  it("keeps every item at full size with overflow none", () => {
    expect(fitToolbar(measure(600), { overflow: "none" })).toMatchObject({
      stage: "none",
      inline: 13,
    });
  });

  it("does not collapse anything before the bar has a width (not laid out)", () => {
    expect(fitToolbar(measure(0))).toMatchObject({ stage: "none", inline: 13 });
  });
});
