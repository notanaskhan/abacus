import type { JSX } from "react";
import { DataGrid } from "../data/data-grid";
import type { TableColumn, TableRow } from "../data/types";
import { Sheet } from "./frame";
import { NORTHWIND_FIGURES, NORTHWIND_PLAN } from "./seed-figures";

// C-01 Data Kit (F-05-T27, data from F-05-T33): the ledger and statement grammars on the E4
// engine, drawing the Brightwater Hale seed's Northwind PY2025 figures (seed-figures.ts), never the
// kit's sample data. Totals are the seed's own figures, as a server would send them; the grid adds
// nothing up, and the app's seed test checks that the ledger's footing holds.

export const LEDGER_COLUMNS: TableColumn[] = [
  { key: "item", header: "Item", type: "label" },
  { key: "amount", header: "Amount", width: 160 },
];

export const LEDGER_ROWS: TableRow[] = [
  {
    id: "unadjusted",
    label: "Net assets available for benefits, unadjusted",
    cells: { amount: { value: NORTHWIND_FIGURES.netAssetsUnadjusted } },
  },
  { id: "adj", kind: "group", label: "Adjustments", cells: {} },
  {
    id: "receivable",
    label: "Contributions receivable",
    indent: 1,
    cells: { amount: { value: NORTHWIND_FIGURES.contributionsReceivable } },
  },
  {
    id: "adjusted",
    kind: "total",
    label: "Net assets available for benefits",
    cells: { amount: { value: NORTHWIND_FIGURES.netAssetsAvailable20251231 } },
  },
];

const STATEMENT_COLUMNS: TableColumn[] = [
  { key: "line", header: NORTHWIND_PLAN, entity: true },
  { key: "end", header: "Dec 31, 2025", width: 140 },
  { key: "start", header: "Jan 1, 2025", width: 140 },
];

const STATEMENT_ROWS: TableRow[] = [
  { id: "g", kind: "group", label: "Statement of net assets available for benefits", cells: {} },
  {
    id: "receivable",
    label: "Contributions receivable",
    indent: 1,
    cells: { end: { value: NORTHWIND_FIGURES.contributionsReceivable }, start: { value: null } },
  },
  {
    id: "net",
    kind: "grand",
    label: "Net assets available for benefits",
    cells: {
      end: { value: NORTHWIND_FIGURES.netAssetsAvailable20251231 },
      start: { value: NORTHWIND_FIGURES.netAssetsAvailable20250101 },
    },
  },
];

export function LedgerGridSpecimen(): JSX.Element {
  return (
    <Sheet title="Ledger grammar" meta="30px rows · 12.5px · $ with cents · ↑↓ select · ↵ open">
      <DataGrid
        label="Operating Checking ••4410, Aug 31"
        columns={LEDGER_COLUMNS}
        rows={LEDGER_ROWS}
      />
    </Sheet>
  );
}

export function StatementGridSpecimen(): JSX.Element {
  return (
    <Sheet title="Statement grammar" meta="th 30 · td 26 · whole dollars · — for zero">
      <DataGrid
        label="Northwind statement of net assets"
        grammar="statement"
        columns={STATEMENT_COLUMNS}
        rows={STATEMENT_ROWS}
      />
    </Sheet>
  );
}
