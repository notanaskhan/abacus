// The firm toolbar's nav overflow (C-00 `overflow-fit.ts`, SHL-01, DF-39; F-05-T18). Pure: the
// component measures widths and this decides, so the order is testable with plain numbers.
//
// The nav never wraps and its type never shrinks. When the bar is too narrow the toolbar gives
// way in the order DF-39 fixes (SHL-01 "NAV WIDTH TEST", plan 04 3.11), and stops at the first
// step where the nav fits:
//
//   0  nothing                        every item inline, the firm pill at its full name
//   1  firm-short                     the firm pill shows the short name ("Brightwater")
//   2  home-pill                      Home leaves the nav for a 30px house pill after Go...
//   3  signatures                     "Signatures" moves into "More"
//   4  signatures-closes-audits       "Signatures", "Closes" and "Audits" move into "More"
//   5  narrow                         trailing items move into "More" one at a time, as many as
//                                     do not fit (the 1080px strip of the bundle)
//
// Overflow is always a trailing run of the nav's order, so "More" lists items in nav order.

/** The nav's gap between items (px). */
export const NAV_GAP = 1;
/** One px of safety each side of the nav's width (the bundle's `fitNav`). */
export const NAV_SAFETY = 2;
/** The bar's padding each side and the gap between its three zones and inside a cluster (px). */
export const BAR_EDGE = 12;
export const BAR_GAP = 8;

export interface FitInput {
  /** Width of each nav item measured at font-weight 500 with padding 0 12 (px), in nav order. */
  itemWidths: readonly number[];
  /** Width of the "More" pill at weight 500. */
  moreWidth: number;
  /** The space the nav has between the left and right clusters (px). */
  navWidth: number;
  /** `none` keeps every item (width tests). */
  overflow?: "auto" | "none";
}

/** How many leading items stay visible; items[n..] go into the More menu. The bundle's `fitNav`. */
export function fitNav({ itemWidths, moreWidth, navWidth, overflow = "auto" }: FitInput): number {
  const avail = navWidth - NAV_SAFETY;
  const total = itemWidths.reduce((a, b) => a + b, 0) + (itemWidths.length - 1) * NAV_GAP;
  if (total <= avail || overflow === "none") return itemWidths.length;
  let sum = moreWidth;
  let n = 0;
  for (const width of itemWidths) {
    const next = sum + NAV_GAP + width;
    if (next > avail) break;
    sum = next;
    n += 1;
  }
  return n;
}

/** The fallback steps, in the order DF-39 applies them. */
export const FALLBACK_STAGES = [
  "none",
  "firm-short",
  "home-pill",
  "signatures",
  "signatures-closes-audits",
  "narrow",
] as const;
export type FallbackStage = (typeof FALLBACK_STAGES)[number];

/** Widths, in px, of everything on the bar. Nothing here depends on the step chosen. */
export interface ToolbarMeasure {
  /** The bar's own width. 0 means "not laid out yet": nothing overflows. */
  barWidth: number;
  go: number;
  /** The firm pill with the full name, and with the short name. */
  firm: number;
  firmShort: number;
  /** The house pill (30). */
  homePill: number;
  support: number;
  bell: number;
  /** Each nav item at weight 500, in nav order (item 0 is Home). */
  items: readonly number[];
  /** The "More" pill. */
  more: number;
}

export interface ToolbarFit {
  stage: FallbackStage;
  /** The firm pill shows the short name. */
  firmShort: boolean;
  /** Home is the house pill, not a nav item. */
  homePill: boolean;
  /** How many leading items (counting Home) are on the bar; items[inline..] are in More. */
  inline: number;
}

/** The space the nav gets at a step: the bar less its padding, its two gaps and both clusters. */
export function navSpace(
  m: ToolbarMeasure,
  { firmShort, homePill }: Pick<ToolbarFit, "firmShort" | "homePill">,
): number {
  const left =
    m.go + BAR_GAP + (homePill ? m.homePill + BAR_GAP : 0) + (firmShort ? m.firmShort : m.firm);
  const right = m.support + BAR_GAP + m.bell;
  return m.barWidth - 2 * BAR_EDGE - 2 * BAR_GAP - left - right;
}

// The nav's own width for `count` leading items (Home excluded when it is the house pill), with
// the More pill when something is left out.
function navNeeds(m: ToolbarMeasure, from: number, count: number): number {
  const shown = m.items.slice(from, count);
  const more = count < m.items.length;
  const widths = shown.reduce((a, b) => a + b, 0) + Math.max(shown.length - 1, 0) * NAV_GAP;
  return widths + (more ? (shown.length > 0 ? NAV_GAP : 0) + m.more : 0);
}

/** The last step of the DF-39 ladder that the caller may skip to: `min` holds the toolbar at a
 * step at least this far (the strips that draw fallback 1 or 2 on purpose). */
export interface FitOptions {
  min?: FallbackStage;
  /** `none` keeps every item and every control at full size (width tests). */
  overflow?: "auto" | "none";
  /** How many items the first collapse and the second collapse take (1, then 3). */
  collapse?: readonly [number, number];
  /** More first (P-01-T02, DF-39 as SHL-01a draws it at 1400): Signatures, then Signatures,
   * Closes and Audits go into More while the firm pill keeps its full name and Home stays in the
   * nav; only after that does the pill shorten and Home become the house pill. */
  moreFirst?: boolean;
}

/** Apply the DF-39 ladder to measured widths: the first step at which the nav fits. */
export function fitToolbar(m: ToolbarMeasure, options: FitOptions = {}): ToolbarFit {
  const n = m.items.length;
  const min = FALLBACK_STAGES.indexOf(options.min ?? "none");
  const [first, second] = options.collapse ?? [1, 3];
  const full: ToolbarFit = { stage: "none", firmShort: false, homePill: false, inline: n };
  if (options.overflow === "none" || m.barWidth <= 0) {
    // Not measured, or told to keep everything: forced steps still apply to the controls.
    return min === 0 ? full : { ...ladder(min, n, first, second), inline: n };
  }
  const steps: ToolbarFit[] =
    options.moreFirst === true
      ? moreFirstSteps(n, first, second)
      : [0, 1, 2, 3, 4].map((i) => ladder(i, n, first, second));
  for (const step of steps) {
    if (FALLBACK_STAGES.indexOf(step.stage) < min) continue;
    const from = step.homePill ? 1 : 0;
    if (navNeeds(m, from, step.inline) <= navSpace(m, step) - NAV_SAFETY) return step;
  }
  // Step 5: the controls are as small as they get; keep as many leading items as fit.
  const last = ladder(2, n, first, second);
  const space = navSpace(m, last);
  const kept = fitNav({
    itemWidths: m.items.slice(1),
    moreWidth: m.more,
    navWidth: space,
  });
  return { stage: "narrow", firmShort: true, homePill: true, inline: 1 + kept };
}

function ladder(i: number, n: number, first: number, second: number): ToolbarFit {
  const stage = FALLBACK_STAGES[i] ?? "none";
  return {
    stage,
    firmShort: i >= 1,
    homePill: i >= 2,
    inline: i === 3 ? Math.max(1, n - first) : i === 4 ? Math.max(1, n - second) : n,
  };
}

// DF-39 with More first: the nav gives up Signatures, then Closes and Audits, before the controls
// shrink; the controls then shrink with those three still in More.
function moreFirstSteps(n: number, first: number, second: number): ToolbarFit[] {
  const one = Math.max(1, n - first);
  const three = Math.max(1, n - second);
  return [
    { stage: "none", firmShort: false, homePill: false, inline: n },
    { stage: "signatures", firmShort: false, homePill: false, inline: one },
    { stage: "signatures-closes-audits", firmShort: false, homePill: false, inline: three },
    { stage: "signatures-closes-audits", firmShort: true, homePill: false, inline: three },
    { stage: "signatures-closes-audits", firmShort: true, homePill: true, inline: three },
  ];
}
