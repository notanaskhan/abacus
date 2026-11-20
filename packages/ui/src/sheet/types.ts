import type { ReactNode } from "react";
import type { Actor } from "../attribution/actor";
import type { CitationView } from "../tracing/types";
import type { StoredCode } from "../status";

// T18 Sheet kit view model (F-08-T05; F-08 §5 "View models"; chapter 03 §3.6). The kit's public
// contract: no API types. Cell status words are the generated `sheet_cell` codes (DF-31, F-08-T04);
// "empty" and "human" are not statuses and carry no pill.

/** The 11 column types (chapter 03 §3.6). */
export type SheetColumnType =
  | "text"
  | "number"
  | "currency"
  | "date"
  | "single_select"
  | "person"
  | "linked_evidence"
  | "linked_request"
  | "linked_risk"
  | "sign_off"
  | "agent";

export type SheetCellState = "empty" | "human" | StoredCode<"sheet_cell">;

export interface SheetGridColumn {
  key: string;
  type: SheetColumnType;
  label: string;
  width: number;
  /** The Key column is frozen with the select column (A1). */
  frozen?: boolean;
  agent?: {
    name: string;
    /** F-08-T07 (DF-04): agents can't run here; the header shows why and offers no run intent. */
    unavailable?: AgentUnavailable;
  };
  /** F-08-T06: the choices of a single select or person column (value is what onCellEdit gets). */
  options?: readonly { value: string; label: string }[];
}

export interface SheetCell {
  /** Display text, already formatted by the consumer (whole numbers, no "$"). */
  value: string;
  state: SheetCellState;
  /** F-08-T06: the editor's starting value when it differs from the display (an ISO date). */
  raw?: string;
  /** F-08-T07, agent cells: who adopted or edited the value, and when ("Oct 1"). */
  by?: Actor;
  at?: string;
  /** F-08-T07, an edited agent cell: the agent's value before the edit. */
  was?: string;
  /** F-08-T07: the citations, from typed C4 locators only (INV-2); never parsed from text. */
  citations?: readonly CitationView[];
  /** F-08-T07: an exception value carries the red flag (C-31). */
  exception?: boolean;
}

/** F-08-T07 (DF-04): why the agent column can't run. */
export type AgentUnavailable = "real_client_data" | "consent_7216";

/** F-08-T07: what the agent column's run shows (adapted from the consumer's E6 RunSource, C6). */
export interface SheetRunState {
  running: boolean;
  /** The rows whose agent cells are still being filled; absent: every empty agent cell. */
  pendingRowKeys?: ReadonlySet<string>;
}

/** A store the grid reads with useSyncExternalStore; the consumer adapts its RunStore to it. */
export interface SheetRunSource {
  subscribe: (listener: () => void) => () => void;
  getSnapshot: () => SheetRunState;
}

export interface SheetSection {
  key: string;
  title: string;
  count: number;
  /** From the server; the kit never sums a column (ADR-050). */
  total?: string;
  sub?: boolean;
}

export interface SheetGridRow {
  key: string;
  sectionKey: string;
  /** Derived by the consumer from sign-off state only (never presence). */
  locked: boolean;
  cells: Record<string, SheetCell>;
  /** F-08-T06: the row version an edit is made against (412/409 when it moved). */
  version?: number;
}

/** F-08-T06: one committed edit; the consumer saves it (optimistic edits are the consumer's). */
export interface SheetCellEdit {
  rowKey: string;
  colKey: string;
  value: string;
  version: number | undefined;
}

/** What `onCellEdit` rejects with when the row moved under the edit (409/412 conflict grammar). */
export interface SheetEditConflict {
  status: 409 | 412;
  changedBy?: string;
}

export interface SheetStatus {
  rows: number;
  exceptions: number;
  view: string;
  agentRunning?: boolean;
  /** F-08-T08: the agent summary at the status bar's right ("3 suggested · 1 adopted"). */
  agentSummary?: string;
}

/** What a header's "···" menu asks the consumer to do; the kit performs none of them. */
export type SheetColumnIntent =
  | { kind: "sort"; dir: "asc" | "desc" }
  | { kind: "filter" }
  | { kind: "hide" }
  | { kind: "edit_agent_column" }
  | { kind: "run_on_empty_rows" };

export interface SheetGridProps {
  columns: readonly SheetGridColumn[];
  sections: readonly SheetSection[];
  rows: readonly SheetGridRow[];
  status: SheetStatus;
  label: string;
  selected?: ReadonlySet<string>;
  onSelect?: (rowKey: string, on: boolean) => void;
  onColumnIntent?: (columnKey: string, intent: SheetColumnIntent) => void;
  filterRow?: boolean;
  /** Scroll viewport height; rows virtualise from 200 (E4). */
  height?: number;
  /** F-08-T06: committing an edit; a rejection with a 409/412 shape shows the conflict row. */
  onCellEdit?: (edit: SheetCellEdit) => Promise<void>;
  /** F-08-T07: the signed-in person; Adopt and Edit render only for a named person (INV-1). */
  viewer?: Actor;
  /** F-08-T07: adopt an agent value (P-35 `suggestion.resolve`); never optimistic (DEC-24). */
  onAdopt?: (rowKey: string, colKey: string) => Promise<void>;
  /** F-08-T07: the consumer opens its editor for an agent value. */
  onEditAgentValue?: (rowKey: string, colKey: string) => void;
  onOpenRow?: (rowKey: string) => void;
  /** F-08-T07: the agent column's run (spinners and "Agent column running"). */
  run?: SheetRunSource;
  /** F-08-T08: a column after the data columns that a template fills (the P · R column). */
  trailing?: SheetTrailingColumn;
}

/** F-08-T08: a template's own column (SheetLayout's 64 px P · R column of C-25 slots). */
export interface SheetTrailingColumn {
  label: string;
  width: number;
  render: (row: SheetGridRow) => ReactNode;
}

/** K-03-T09 (SH-1, C23; F-08 §4): the sheet as the server sends it, in the kit's own shapes, so a
 * `SheetLayout` grid takes it as it comes (`toSheetVM` in apps/web maps the generated client). */
export interface SheetVM {
  sheetId: string;
  workItemId: string;
  title: string;
  columns: readonly SheetGridColumn[];
  sections: readonly SheetSection[];
  rows: readonly SheetGridRow[];
  status: SheetStatus;
  signedOff: boolean;
  allowedActions: readonly string[];
}
