// F-08-T28 (DEC-6026): the T20 document editor's input shapes (F-08 §5 C1, C4). The kit draws
// what its consumer computed (ADR-050): statement rows carry their figures, never a formula to run.
import type { PresencePeer } from "../collab/presence";

/** One row of a read-only statement table (a node view; never typed over). */
export interface StatementRow {
  key: string;
  caption: string;
  indent: 0 | 1 | 2;
  /** The figures for each column, in column order (null: blank). */
  amounts: readonly (number | null)[];
  /** "$" only on a statement's first line and its double-ruled totals. */
  dollar?: boolean;
  rule?: "above" | "double_below";
  /** A caps heading row ("ASSETS"), with no amounts. */
  heading?: boolean;
}

export interface StatementTableAttrs {
  key: string;
  columns: readonly string[];
  rows: readonly StatementRow[];
}

/** A section another person is editing: read-only here, with its banner (ADR P-59, P-15). */
export interface SectionLock {
  section: string;
  label: string;
  peer: PresencePeer;
}
