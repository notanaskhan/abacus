// The T6 WorkbookLayout kit's prop API (F-06-T18; F-06.md §5.2, SPEC-400 AC-26 to AC-32): the
// contract F-06-T19 (calc tree), F-06-T20 (SignOffSlots, TPL-06), F-06-T21 (acceptance tests) and
// the consumers (AUD-08, EBP-04, AUD-16, TXP-07) build against. L2 rule: generic shapes, no
// @abacus/api-client types. Every figure, total, tie and difference is the server's (ADR-050):
// the kit formats and lays out, and never adds.

import type { Opt } from "../../components/tabs";
import type { TableColumn, TableRow } from "../../data/types";
import type { TallyItem } from "../../data/tally-strip";

/** A tally card. `issue` is the issue the card's difference is linked to ("2"): the card gains an
 * "Issue 2" link that calls `onOpenIssue` with it (Story 5.2). */
export type WorkbookTallyItem = TallyItem & { issue?: string };

/** A statement pane's payload, in the E4 shape (rows of decimal strings, totals sent as rows). */
export interface TablePayload {
  /** The table's accessible name. */
  label: string;
  columns: readonly TableColumn[];
  rows: readonly TableRow[];
  /** The 11.5 ink-3 line under the table ("Tax basis · December 31, 2025"). */
  footnote?: string;
}

/** One step of the calculation tree (F-06-T19). `match` comes from a typed xlsx locator (INV-2). */
export interface CalcStep {
  ref: string;
  depth: number;
  /** "", "+", "−", "×". */
  op: string;
  label: string;
  /** Formatted by the server ("938,561", "(148,500)", "—"). */
  value: string;
  /** "Capital!H3" or "Schedule K · line 5". */
  src: string;
  match?: string;
}

export interface WorkbookPaneVM {
  /** `statement` here (F-06-T18); `grid` and `calc` render with F-06-T19. */
  kind: "statement" | "grid" | "calc";
  table?: TablePayload;
  tree?: readonly CalcStep[];
  /** A fixed pane width (452 for the by-partner panes): sized panes sit in the PaneScroller. */
  width?: number;
  /** A sized pane's 46 header title ("Calder Family Trust"). */
  title?: string;
}

/** A sign-off slot (F-06-T20, C-25): the initials chip of a person who signed. */
export interface SignOffSlotVM {
  level: string;
  initials: string;
  name: string;
  when?: string;
  stale?: boolean;
}

export interface WorkbookVM {
  views: readonly Opt[];
  view: string;
  title: string;
  /** Values and results from the server. */
  tally: readonly WorkbookTallyItem[];
  panes: readonly WorkbookPaneVM[];
  signOffs?: readonly SignOffSlotVM[];
  /** The agent is building the schedule: the running row's words ("Workbook agent is running").
   * Pills read Pending, rows are skeletons, and no sign-off control is enabled (Story 5.4). */
  building?: { label: string };
}

/** The kit's words, from the consumer's copy module (T6/copy.ts). */
export interface WorkbookCopy {
  openInExcel: string;
  download: string;
  signOff: string;
  /** The view segmented's accessible name ("Capital accounts view"). */
  views: string;
  /** The pane scroller's accessible name ("Partners"). */
  scroller: string;
}
