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
}

export interface SheetCell {
  /** Display text, already formatted by the consumer (whole numbers, no "$"). */
  value: string;
  state: SheetCellState;
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
  locked: boolean;
  cells: Record<string, SheetCell>;
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
}
