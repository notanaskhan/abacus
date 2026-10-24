// C-02 Workpaper kit and the C-15 source-document rows (F-05-T50): generic view models. A screen
// maps its workpaper, its citations (C4) and its request items into these; nothing here imports the
// API client. Every match id comes from a typed locator (INV-2): a table cell's through
// `matchIdOf({ kind: "workpaper_cell", ... })`, a citation's off the C4 citation.

import type { TableColumn, TableRow } from "../data/types";
import type { CitationView, ProcedureRef } from "../tracing";

/** One key/value row: "Procedure performed", "Result", "Conclusion". */
export interface WorkpaperKv {
  key: string;
  text: string;
  /** Citation numbers drawn as markers after the text. */
  cites?: readonly number[];
}

/** A section's evidence table: the C-01 evidence grammar, pad 14, no card. */
export interface WorkpaperTable {
  columns: readonly TableColumn[];
  rows: readonly TableRow[];
}

/** One numbered section: band, caption, key/value rows, schedule bar, table, after-rows. */
export interface WorkpaperSectionData {
  id: string;
  /** The band reads "SECTION {n} — {TITLE}". */
  n?: number;
  title: string;
  /** Replaces the generated band label. */
  label?: string;
  /** The sign-off micro text after a check: "Prepared · Accrued Agent". */
  sign?: string;
  /** Default true: the band is one native button. */
  collapsible?: boolean;
  /** The initial state. */
  collapsed?: boolean;
  caption?: string;
  rows?: readonly WorkpaperKv[];
  /** The supporting-schedule title bar over the table. */
  schedule?: string;
  table?: WorkpaperTable;
  /** Key/value rows after the table; the first draws a hair above it. */
  after?: readonly WorkpaperKv[];
}

/** One tab of a workpaper: its sections, the citations its markers open and its procedures. */
export interface WorkpaperTab {
  label: string;
  /** The workpaper sheet the tab's cells belong to: the `sheet_id` of their locators. */
  sheet: string;
  sections: readonly WorkpaperSectionData[];
  citations?: readonly CitationView[];
  procedures?: readonly ProcedureRef[];
}

/** Where a requested source document stands (C-15; the C2 request words, collapsed). */
export type SourceDocStatus = "received" | "review" | "requested";

/** A source document as the canvas lists it: a request item and the file that answers it. */
export interface SourceDoc {
  id: string;
  title: string;
  /** The received file's path ("initial-input/…"); absent until a file arrives. */
  path?: string;
  status: SourceDocStatus;
}

/** `cockpit`: the T2 canvas (TPL-02: band 31, rows 52). `compact`: the C-15 kit (band 32, rows 40). */
export type SourceDocSize = "cockpit" | "compact";
