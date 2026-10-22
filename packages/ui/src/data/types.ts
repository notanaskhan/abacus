// E4 DataTable (F-05-T27; plan 04 E4; C-01 Data Kit): the shapes a table payload carries. They
// follow the E4 backend contract: rows of `{id, kind, label, indent, cells}` with decimal strings.
// Totals are rows the server sends (`kind: "total" | "grand"`); the table never adds anything up
// (ADR-050: code computes, and that code is on the server).

import type { AmountStyle } from "../format";

/** The five grammars of E4. This task builds the engine with `ledger` and `statement`. */
export type Grammar = "ledger" | "statement";

export type ColumnType = "label" | "text" | "num" | "chip";

export interface TableColumn {
  key: string;
  header: string;
  /** Default: the first column is `label`, the rest `num`. */
  type?: ColumnType | undefined;
  /** px; omitted is auto. Numbers are never truncated: widen the column instead. */
  width?: number | undefined;
  align?: "left" | "right" | undefined;
  /** Overrides the grammar's number format. */
  format?: AmountStyle | undefined;
  /** A money column with tickmarks: room on the right for the tick, pinned 10 from the edge. */
  tick?: boolean | undefined;
  /** The first header names the entity: 13/500 ink instead of the th style (statement). */
  entity?: boolean | undefined;
}

export type RowKind = "item" | "group" | "total" | "grand";

/** A tickmark (C-01): `MS` and `Received` are green pills with a check, `check` a bare check. */
export type Tickmark = "MS" | "Received" | "PY" | "TB" | "F" | "check";

export interface TableCell {
  /** A decimal string ("1234.56"), a text value, or null for blank. */
  value: string | null;
  tick?: Tickmark | undefined;
}

export interface TableRow {
  id: string;
  kind?: RowKind | undefined;
  label: string;
  /** Label padding-left = grammar pad + indent × the grammar's indent step. */
  indent?: number | undefined;
  /** A micro tag after the label (GP, LP). */
  tag?: string | undefined;
  cells: Readonly<Record<string, TableCell | undefined>>;
}
