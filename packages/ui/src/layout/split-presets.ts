// SplitLayout presets as data (F-05-T29; plan 04 §3.11; C-09). The widths are chapter 04's, at
// the 1440 design width. Where the C-09 kit draws a column as `flex`, it flexes from the plan's
// width as its basis, so a 1440 window shows the plan's numbers and a wider or narrower one
// stretches those columns; fixed columns hold their width until resized.

export interface PresetPane {
  /** The design width in px (plan 04 §3.11). */
  width: number;
  /** Grows and shrinks from `width` (C-09 `flex`). */
  flex?: boolean;
  /** A flex pane's minimum; 280 by default. */
  min?: number;
}

export interface SplitPreset {
  panes: readonly PresetPane[];
  /** At 1280 or less the third column becomes a right drawer. */
  drawer?: boolean;
  /** False draws no gutters (C-11 library). */
  resizable?: boolean;
}

export const SPLIT = {
  gutter: 10,
  minPane: 280,
  maxPaneRatio: 0.6,
  nudge: 16,
  narrowAt: 1280,
} as const;

export const SPLIT_PRESETS = {
  audit: { drawer: true, panes: [{ width: 330 }, { width: 536 }, { width: 490 }] },
  "audit-chat": {
    drawer: true,
    panes: [{ width: 330 }, { width: 696 }, { width: 330, flex: true, min: 330 }],
  },
  taxReview: {
    drawer: true,
    panes: [{ width: 214 }, { width: 571, flex: true }, { width: 571, flex: true }],
  },
  review: { panes: [{ width: 452 }, { width: 452, flex: true }, { width: 452, flex: true }] },
  "issues-individual": {
    drawer: true,
    panes: [{ width: 546 }, { width: 433, flex: true }, { width: 377, flex: true }],
  },
  "close-review": { panes: [{ width: 790 }, { width: 576, flex: true }] },
  "issues-entity": { panes: [{ width: 470 }, { width: 896, flex: true }] },
  // T10 DocumentOnWell (F-06-T14): the 470 structure pane beside the 896 paper pane.
  document: { panes: [{ width: 470 }, { width: 896, flex: true }] },
  workbench: { panes: [{ width: 358 }, { width: 998, flex: true }] },
  agents: { panes: [{ width: 320 }, { width: 1036, flex: true }] },
  library: { resizable: false, panes: [{ width: 358 }, { width: 998, flex: true }] },
  inbox: { panes: [{ width: 392 }, { width: 964, flex: true }] },
  portal: { panes: [{ width: 336 }, { width: 1020, flex: true }] },
} as const satisfies Record<string, SplitPreset>;

export type SplitPresetName = keyof typeof SPLIT_PRESETS;

/** Saved widths live under this key, as `{paneIndex: px}`; an empty record removes the key. */
export function splitStorageKey(preset: SplitPresetName): string {
  return `split.${preset}`;
}

/** Is pane `i` fixed (a preset width or a saved one)? */
function fixed(
  panes: readonly PresetPane[],
  overrides: Readonly<Record<number, number>>,
  i: number,
): boolean {
  return overrides[i] !== undefined || panes[i]?.flex !== true;
}

/**
 * The pane a gutter resizes: the fixed neighbour, the left one first; when both are flex the
 * left pane becomes fixed. `sign` is +1 when moving the gutter right widens the target.
 */
export function dragTarget(
  gutter: number,
  panes: readonly PresetPane[],
  overrides: Readonly<Record<number, number>>,
): { target: number; sign: 1 | -1 } {
  if (fixed(panes, overrides, gutter)) return { target: gutter, sign: 1 };
  if (fixed(panes, overrides, gutter + 1)) return { target: gutter + 1, sign: -1 };
  return { target: gutter, sign: 1 };
}

/**
 * The widest pane `target` may be: the smaller of 60% of the row and the room the other panes
 * leave (their widths, the gutters, and 280 for each flex pane). At least 280. With no measured
 * row (0), only the floor applies.
 */
export function roomFor(
  rowInner: number,
  panes: readonly PresetPane[],
  overrides: Readonly<Record<number, number>>,
  target: number,
): number {
  if (rowInner <= 0) return Number.POSITIVE_INFINITY;
  let others = 0;
  panes.forEach((p, i) => {
    if (i === target) return;
    others += overrides[i] ?? (p.flex === true ? (p.min ?? SPLIT.minPane) : p.width);
  });
  const room = rowInner - SPLIT.gutter * (panes.length - 1) - others;
  return Math.max(SPLIT.minPane, Math.min(Math.round(rowInner * SPLIT.maxPaneRatio), room));
}

/** Clamp a width for `target` between min(280, its design width) and `roomFor`. */
export function clampWidth(
  width: number,
  rowInner: number,
  panes: readonly PresetPane[],
  overrides: Readonly<Record<number, number>>,
  target: number,
): number {
  const floor = Math.min(SPLIT.minPane, panes[target]?.width ?? SPLIT.minPane);
  return Math.round(Math.max(floor, Math.min(width, roomFor(rowInner, panes, overrides, target))));
}
