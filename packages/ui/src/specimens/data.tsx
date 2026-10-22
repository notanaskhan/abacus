import type { JSX } from "react";
import { DataGrid } from "../data/data-grid";
import type { TableColumn, TableRow } from "../data/types";
import { Sheet } from "./frame";

// C-01 Data Kit (F-05-T27): the ledger grammar (the kit's bank-rec sample) and the statement
// grammar (its Schedule L), on the E4 engine. Totals are the sample's own figures, as a server
// would send them; the grid adds nothing up.

const LEDGER_COLUMNS: TableColumn[] = [
  { key: "date", header: "Date", type: "text", width: 76 },
  { key: "item", header: "Item", type: "label" },
  { key: "ref", header: "Reference", type: "text", width: 176 },
  { key: "amount", header: "Amount", width: 132 },
];

const LEDGER_ROWS: TableRow[] = [
  {
    id: "bal",
    label: "Balance per bank",
    cells: { date: { value: "Aug 31" }, amount: { value: "52410.07" } },
  },
  { id: "out", kind: "group", label: "Outstanding checks", cells: {} },
  {
    id: "c1",
    label: "Check 2214 · Alpine Supply",
    indent: 1,
    cells: { date: { value: "Aug 28" }, ref: { value: "2214" }, amount: { value: "-810" } },
  },
  {
    id: "c2",
    label: "Check 2215 · Summit Freight",
    indent: 1,
    cells: { date: { value: "Aug 29" }, ref: { value: "2215" }, amount: { value: "-2140.5" } },
  },
  {
    id: "c3",
    label: "Check 2217 · Payroll",
    indent: 1,
    cells: { date: { value: "Aug 30" }, ref: { value: "2217" }, amount: { value: "-1249.5" } },
  },
  {
    id: "adj",
    kind: "total",
    label: "Adjusted bank balance",
    cells: { amount: { value: "48210.07" } },
  },
];

const STATEMENT_COLUMNS: TableColumn[] = [
  { key: "line", header: "Ridgeline Property Partners, LP", entity: true },
  { key: "tax", header: "Tax", width: 120 },
  { key: "book", header: "704(b)", width: 120 },
];

const STATEMENT_ROWS: TableRow[] = [
  { id: "a", kind: "group", label: "Assets", cells: {} },
  {
    id: "cash",
    label: "Cash",
    indent: 1,
    cells: { tax: { value: "412880" }, book: { value: "412880" } },
  },
  {
    id: "bld",
    label: "Buildings and other depreciable assets",
    indent: 1,
    cells: { tax: { value: "9840000" }, book: { value: "9840000" } },
  },
  {
    id: "dep",
    label: "Less accumulated depreciation",
    indent: 1,
    cells: { tax: { value: "-1486212" }, book: { value: "-1290400" } },
  },
  {
    id: "oth",
    label: "Other assets",
    indent: 1,
    cells: { tax: { value: "0" }, book: { value: "0" } },
  },
  {
    id: "ta",
    kind: "grand",
    label: "Total assets",
    cells: { tax: { value: "8766668" }, book: { value: "8962480" } },
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
        label="Schedule L"
        grammar="statement"
        columns={STATEMENT_COLUMNS}
        rows={STATEMENT_ROWS}
      />
    </Sheet>
  );
}
