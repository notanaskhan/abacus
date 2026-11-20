// Shared fixtures for the F-08-T11 acceptance tests (TASK-8750; ADR-078). Built from types.ts and
// the F-08 §3 A2–A3 ACs only: TPL-20's SURL columns, two rows, a signed-off one locked.
import { render } from "@testing-library/react";
import type { Actor } from "../../attribution/actor";
import { SheetGrid } from "../SheetGrid";
import type { SheetGridColumn, SheetGridProps, SheetGridRow, SheetSection } from "../types";

export const COLE: Actor = { kind: "human", name: "Cole Hart" };
export const LOCK_COPY =
  "Signed-off rows are locked. Sign-offs are removed only from the sign-off modal.";

export const COLUMNS: SheetGridColumn[] = [
  { key: "key", type: "text", label: "Key", width: 96, frozen: true },
  { key: "vendor", type: "text", label: "Vendor", width: 200 },
  { key: "amount", type: "currency", label: "Amount", width: 110 },
  {
    key: "conclusion",
    type: "agent",
    label: "Conclusion",
    width: 180,
    agent: { name: "Unrecorded liabilities tester" },
  },
];
export const SECTIONS: SheetSection[] = [{ key: "s1", title: "Stratum 1", count: 2 }];

export function surlRow(
  key: string,
  locked: boolean,
  conclusion: SheetGridRow["cells"][string] = { value: "Properly excluded", state: "suggested" },
): SheetGridRow {
  return {
    key,
    sectionKey: "s1",
    locked,
    version: 3,
    cells: {
      key: { value: key, state: "human" },
      vendor: { value: "Front Range Freight Co.", state: "human" },
      amount: { value: "68,400", state: "human" },
      conclusion,
    },
  };
}

export function grid(over: Partial<SheetGridProps> = {}) {
  const props: SheetGridProps = {
    columns: COLUMNS,
    sections: SECTIONS,
    rows: [surlRow("SURL-04", false), surlRow("SURL-05", true)],
    status: { rows: 2, exceptions: 0, view: "All rows" },
    label: "BH-FS-430",
    viewer: COLE,
    ...over,
  };
  return { props, ...render(<SheetGrid {...props} />) };
}

export function cellOf(rowKey: string, colKey: string): HTMLElement {
  const el = document.querySelector<HTMLElement>(
    `[data-row-key="${rowKey}"] [data-col-key="${colKey}"]`,
  );
  if (el === null) throw new Error(`no cell ${rowKey}/${colKey}`);
  return el;
}
