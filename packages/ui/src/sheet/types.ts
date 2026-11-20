// T18 Sheet kit view model (F-08-T05; F-08 §5 "View models"; chapter 03 §3.6). The kit's public
// contract: no API types. Status words stay kit-local drafts until the DF-31 PR (F-08-T04).

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

export type SheetCellState = "empty" | "human" | "suggested" | "adopted" | "edited";

export interface SheetGridColumn {
  key: string;
  type: SheetColumnType;
  label: string;
  width: number;
  /** The Key column is frozen with the select column (A1). */
  frozen?: boolean;
  agent?: { name: string };
  /** F-08-T06: the choices of a single select or person column (value is what onCellEdit gets). */
  options?: readonly { value: string; label: string }[];
}

export interface SheetCell {
  /** Display text, already formatted by the consumer (whole numbers, no "$"). */
  value: string;
  state: SheetCellState;
  /** F-08-T06: the editor's starting value when it differs from the display (an ISO date). */
  raw?: string;
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
}
