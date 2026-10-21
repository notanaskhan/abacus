import { DASH, count, ratio } from "../format";

// The rules of the C-19 Progress kit, as pure functions (F-05-T19). The components in
// progress.tsx only draw what these return; progress-model.test.ts holds the cases from the
// bundle's IMPLEMENTATION step 1. Every number is shown whole (a percent never has a decimal) and
// with thousands separators (format.ts `count`).

/** Whole percent, rounded half up. 0 when there is no total. Not clamped, as `progress()` is not. */
export function percentOf(done: number, total: number): number {
  if (total <= 0 || done <= 0) return 0;
  return Math.floor((done * 200 + total) / (total * 2));
}

// ---- ProgressBar ------------------------------------------------------------------------------

/** Espresso is the default; amber is for uploads and anything in progress. Never green. */
export type BarTone = "ink" | "amber";

/** The left label of a bar whose total is not known yet. */
export const INDETERMINATE_LABEL = "Counting files…";

export interface BarView {
  /** True only while the total is unknown. */
  indeterminate: boolean;
  /** The fill's width, `62%`; null when indeterminate. */
  width: string | null;
  /** "9 of 13 complete", "7 of 18 files uploaded"; or the caller's own left label. */
  left: string;
  aria: {
    "aria-valuemin"?: 0;
    "aria-valuemax"?: number;
    "aria-valuenow"?: number;
    "aria-busy"?: true;
    "aria-label": string;
  };
}

/**
 * A progress bar's label, width and ARIA (C-19 spec 1). Every bar says "n of N": the left label
 * is that, with a noun ("files uploaded") or "complete". A null total makes it indeterminate: no
 * `aria-valuenow`, `aria-busy`, and the label reads "Counting files…" unless the caller says more.
 */
export function barView(
  done: number,
  total: number | null,
  options: { noun?: string | undefined; left?: string | undefined } = {},
): BarView {
  if (total === null) {
    const left = options.left ?? INDETERMINATE_LABEL;
    return {
      indeterminate: true,
      width: null,
      left,
      aria: { "aria-busy": true, "aria-label": left },
    };
  }
  const left = options.left ?? `${count(done)} of ${count(total)} ${options.noun ?? "complete"}`;
  const fill = Math.min(100, Math.max(0, percentOf(done, total)));
  return {
    indeterminate: false,
    width: `${String(fill)}%`,
    left,
    aria: {
      "aria-valuemin": 0,
      "aria-valuemax": total,
      "aria-valuenow": done,
      "aria-label": `${String(done)} of ${String(total)}`,
    },
  };
}

// ---- UploadRing -------------------------------------------------------------------------------

/** The ring's radius and circumference in its 50px box. */
export const RING_RADIUS = 22;
export const RING_CIRCUMFERENCE = 2 * Math.PI * RING_RADIUS;

export interface RingView {
  /** Dash offset: the whole circumference at 0, nothing at 1. */
  offset: number;
  /** The arc is hidden at 0, where a round cap would leave a dot at 12 o'clock. */
  arc: boolean;
  /** True from 1: the arc and the file fade out and the olive check disc fades in. */
  done: boolean;
  /** 0 to 100, for `aria-valuenow`. */
  valueNow: number;
}

export function ringView(fraction: number): RingView {
  const f = Math.min(1, Math.max(0, fraction));
  return {
    offset: RING_CIRCUMFERENCE * (1 - f),
    arc: f > 0,
    done: fraction >= 1,
    valueNow: Math.round(f * 100),
  };
}

// ---- StepCounter ------------------------------------------------------------------------------

export type StepState = "done" | "progress" | "pending";

export interface StepInput {
  name: string;
  done: number;
  /** Zero or less: the total is not known yet. */
  total: number;
}

export interface StepView {
  name: string;
  state: StepState;
  /** "312 of 312 · 100%", or a dash with no total. */
  counter: string;
}

/**
 * The steps of an agent run (C-19 spec 5). A step is done when it has reached its total; the
 * first step that is not done is in progress and every later one is pending.
 */
export function stepViews(steps: readonly StepInput[]): StepView[] {
  let seen = false;
  return steps.map(({ name, done, total }) => {
    const finished = total > 0 && done >= total;
    const current = !finished && !seen;
    if (current) seen = true;
    return {
      name,
      state: finished ? "done" : current ? "progress" : "pending",
      counter:
        total > 0
          ? `${count(done)} of ${count(total)} · ${String(percentOf(done, total))}%`
          : DASH,
    };
  });
}

// ---- KPI tile ---------------------------------------------------------------------------------

/**
 * A delta's colour is good or bad, not direction: `good-down` is a fall that is good (unbilled
 * work in progress), `bad` a rise that is bad (open issues). `flat` has no arrow.
 */
export type KpiTone = "good" | "good-down" | "bad" | "bad-down" | "flat";

export interface KpiDelta {
  arrow: "up" | "down" | null;
  judgement: "good" | "bad" | "flat";
}

export function kpiDelta(tone: KpiTone): KpiDelta {
  return {
    arrow: tone === "good" || tone === "bad" ? "up" : tone === "flat" ? null : "down",
    judgement: tone === "flat" ? "flat" : tone.startsWith("good") ? "good" : "bad",
  };
}

/** The sparkline's box and the points of its line: x from 2 to 74, y from 21 (min) to 3 (max). */
export const SPARK_WIDTH = 76;
export const SPARK_HEIGHT = 24;

export function sparkPoints(values: readonly number[]): string {
  if (values.length < 2) return "";
  const lo = Math.min(...values);
  const hi = Math.max(...values);
  const span = hi - lo === 0 ? 1 : hi - lo;
  return values
    .map((v, i) => {
      const x = 2 + i * (72 / (values.length - 1));
      const y = 21 - ((v - lo) / span) * 18;
      return `${ratio(x, 1)},${ratio(y, 1)}`;
    })
    .join(" ");
}

// ---- StatusTile -------------------------------------------------------------------------------

/** A tile's pill label longer than this many characters drops to 10.5px with tighter padding. */
export const LONG_PILL_CHARS = 14;

export const isLongPillLabel = (label: string): boolean => label.length > LONG_PILL_CHARS;

/**
 * Open work on the practice strip: the tiles' counts plus the returns that have no tile ("Not
 * started"). 17 + 15 + 11 + 7 + 8 + 9 + 10 + 2 = 79; with 145 filed that is 224.
 */
export function practiceOpen(tileCounts: readonly number[], withoutTile = 0): number {
  return tileCounts.reduce((sum, n) => sum + n, withoutTile);
}
