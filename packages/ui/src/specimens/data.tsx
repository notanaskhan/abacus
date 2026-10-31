import type { JSX } from "react";
import { type AccountSection, AccountTree } from "../data/account-tree";
import { DataGrid } from "../data/data-grid";
import { EvidenceTable } from "../data/evidence";
import { MappingTable } from "../data/mapping-table";
import { Icon } from "../icons";
import { Pill } from "../components/pill";
import { TallyStrip } from "../data/tally-strip";
import type { TableColumn, TableRow, VarianceValue } from "../data/types";
import { Row, Sheet } from "./frame";
import {
  NORTHWIND_CHANGE,
  NORTHWIND_FIGURES,
  NORTHWIND_PLAN,
  REQUEST_COUNTS,
  STAFF,
} from "./seed-figures";

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

// ---- F-05-T43: evidence grammar, variance, TallyStrip, AccountTree --------------------------------

const EVIDENCE_COLUMNS: TableColumn[] = [
  { key: "line", header: "Description", type: "label" },
  { key: "source", header: "Source", type: "chip", width: 120 },
  { key: "end", header: "Dec 31, 2025", width: 180, tick: true },
  { key: "start", header: "Jan 1, 2025", width: 180, tick: true },
];

const EVIDENCE_ROWS: TableRow[] = [
  { id: "g", kind: "group", label: "Net assets", cells: {} },
  {
    id: "unadjusted",
    label: "Net assets available for benefits, unadjusted",
    indent: 1,
    cells: {
      source: { value: "Trust report" },
      end: { value: NORTHWIND_FIGURES.netAssetsUnadjusted, tick: "MS" },
      start: { value: null },
    },
  },
  {
    id: "receivable",
    label: "Contributions receivable",
    indent: 1,
    cells: {
      source: { value: "TB" },
      end: { value: NORTHWIND_FIGURES.contributionsReceivable, tick: "check" },
      start: { value: null },
    },
  },
  {
    id: "net",
    kind: "total",
    label: "Net assets available for benefits",
    cells: {
      end: { value: NORTHWIND_FIGURES.netAssetsAvailable20251231, tick: "F" },
      start: { value: NORTHWIND_FIGURES.netAssetsAvailable20250101, tick: "PY" },
    },
  },
];

export function EvidenceGridSpecimen(): JSX.Element {
  return (
    <Sheet title="Evidence grammar" meta="Blocks on a well · th 28 · td 29 · $ with cents · ticks">
      <Row name="Cards on a well" meaning="Block header 32; extracted-value chips; pinned ticks">
        <div className="w-[760px] max-w-full overflow-hidden rounded-pane">
          <EvidenceTable
            label="Trial Balance"
            blocks={[
              {
                id: "net-assets",
                title: "Net assets available for benefits",
                meta: NORTHWIND_PLAN,
                columns: EVIDENCE_COLUMNS,
                rows: EVIDENCE_ROWS,
              },
            ]}
          />
        </div>
      </Row>
    </Sheet>
  );
}

const VARIANCE_COLUMNS: TableColumn[] = [
  { key: "item", header: "State", type: "label" },
  { key: "change", header: "Change", type: "variance", width: 220 },
];

const CHANGE: VarianceValue = {
  value: NORTHWIND_CHANGE.netAssetsChange,
  ratio: NORTHWIND_CHANGE.ratio,
  threshold: "0",
};

const VARIANCE_ROWS: TableRow[] = [
  {
    id: "within",
    label: "Within threshold",
    cells: { change: { value: null, variance: { value: "0.00", threshold: "0" } } },
  },
  {
    id: "unexplained",
    label: "Unexplained",
    cells: { change: { value: null, variance: CHANGE } },
  },
  {
    id: "explained",
    label: "Explained",
    cells: {
      change: {
        value: null,
        variance: {
          ...CHANGE,
          explained: {
            text: "Contributions and investment income over the plan year.",
            by: STAFF.hannah,
          },
        },
      },
    },
  },
  {
    id: "exception",
    label: "Exception",
    cells: { change: { value: null, variance: { ...CHANGE, exception: { issue: "9" } } } },
  },
  {
    id: "posted",
    label: "Posted",
    cells: { change: { value: null, variance: { ...CHANGE, posted: true } } },
  },
];

export function VarianceSpecimen(): JSX.Element {
  return (
    <Sheet title="Variance cell" meta="Δ · Δ% · glyph; five states, each in words">
      <Row name="Ledger" meaning="Explain… and the issue link in the action column">
        <div className="w-[560px] max-w-full">
          <DataGrid
            label="Northwind change in net assets"
            columns={VARIANCE_COLUMNS}
            rows={VARIANCE_ROWS}
            onExplain={() => undefined}
            onIssue={() => undefined}
          />
        </div>
      </Row>
    </Sheet>
  );
}

const NW = REQUEST_COUNTS.northwind;

export function TallyStripSpecimen(): JSX.Element {
  return (
    <Sheet title="TallyStrip" meta="Cards 52 · label 9.5 uppercase · 45ms stagger">
      <Row name="Checks" meaning="Value, tally pills, running, sign-offs">
        <TallyStrip
          className="w-[1040px] max-w-full"
          label="Northwind checks"
          items={[
            { label: "Trial balance ties", tally: "tie" },
            { label: "Net assets foot", tally: "tie" },
            { label: "Requests received", value: `${String(NW.received)} / ${String(NW.total)}` },
            { label: "Contributions receivable", tally: "check" },
            { label: "Trust report", tally: "pending" },
            { label: "Planning", running: "Running" },
            {
              label: "Signed off",
              signs: [{ initials: "HL", when: "Sep 14", name: STAFF.hannah }],
            },
          ]}
        />
      </Row>
    </Sheet>
  );
}

const ACCOUNTS: readonly AccountSection[] = [
  {
    title: "Net assets",
    accounts: [
      {
        id: "net",
        name: "Net assets available for benefits",
        balance: NORTHWIND_FIGURES.netAssetsAvailable20251231,
        children: [
          {
            id: "unadjusted",
            name: "Net assets, unadjusted",
            balance: NORTHWIND_FIGURES.netAssetsUnadjusted,
          },
          {
            id: "receivable",
            name: "Contributions receivable",
            balance: NORTHWIND_FIGURES.contributionsReceivable,
          },
        ],
      },
    ],
  },
  {
    title: "Roll-forward",
    accounts: [
      {
        id: "rf",
        name: "Net assets available for benefits, Dec 31, 2025",
        balance: NORTHWIND_FIGURES.netAssetsAvailable20251231,
        open: false,
        children: [
          {
            id: "rf-start",
            name: "Net assets available for benefits, Jan 1, 2025",
            balance: NORTHWIND_FIGURES.netAssetsAvailable20250101,
          },
          {
            id: "rf-change",
            name: "Change in net assets",
            balance: NORTHWIND_CHANGE.netAssetsChange,
          },
        ],
      },
    ],
  },
];

export function AccountTreeSpecimen(): JSX.Element {
  return (
    <Sheet title="AccountTree" meta="Rows 37 · indent 12 / 30 / 48 · → opens, ← closes">
      <Row name="Chart" meaning="A collapsed parent; balances are the server's">
        <div className="w-[520px] max-w-full overflow-hidden rounded-pane bg-card shadow-e2">
          <AccountTree label={`${NORTHWIND_PLAN} accounts`} sections={ACCOUNTS} />
        </div>
      </Row>
    </Sheet>
  );
}

// ---- A-03-T12: MappingTable (L2), the AUD-31 sheet ----------------------------------------------

/** Harlow & Pike's six review rows and Manufacturing's PP&E group, verbatim (AUD-31 a). */
export function MappingTableSpecimen(): JSX.Element {
  const marker = (
    <span title="Suggested by Accrued Agent · not yet adopted" className="text-ink-3">
      <Icon name="atom" size={12} label="Suggested by Accrued Agent · not yet adopted" />
    </span>
  );
  return (
    <Sheet title="MappingTable" meta="L2 · AUD-31 · review band 52 · mapped rows 30 · subtotal">
      <Row name="Needs review · mapped by FS line" meaning="Entities, reasons, a group open">
        <MappingTable
          className="w-[876px] max-w-full"
          label="Trial balance mapping"
          entities
          selected="1460"
          review={{
            label: "Needs review · 6",
            rows: [
              {
                id: "1460",
                entity: "Manufacturing",
                code: "1460",
                name: "Tooling deposits",
                balance: "310,000",
                mapped: "Other assets › Deposits",
                suggested: true,
                marker,
                method: "Description",
                confidence: "Low",
                confidenceTone: "amber",
                reason:
                  "No prior-year account; description 'Tooling deposits' suggests Other assets.",
              },
              {
                id: "2215",
                entity: "Distribution",
                code: "2215",
                name: "Customer rebates payable",
                balance: "(145,000)",
                balanceTone: "neg",
                mapped: "Accrued liabilities › Customer rebates",
                suggested: true,
                marker,
                method: "Description",
                confidence: "Medium",
                reason:
                  "No prior-year account; dealer rebates accrued monthly are an accrued liability, not trade payables.",
              },
            ],
          }}
          mapped={{
            label: "Mapped · 238",
            groups: [
              {
                key: "ppe",
                label: "Manufacturing › Property, plant & equipment",
                open: true,
                rows: [
                  {
                    id: "1420",
                    entity: "Manufacturing",
                    code: "1420",
                    name: "Machinery and equipment",
                    balance: "12,600,000",
                    mapped: "PP&E › Machinery and equipment",
                    method: "Prior-year match",
                    confidence: "High",
                  },
                  {
                    id: "1450",
                    entity: "Manufacturing",
                    code: "1450",
                    name: "Accumulated depreciation",
                    balance: "(8,100,000)",
                    balanceTone: "neg",
                    mapped: "PP&E › Accumulated depreciation",
                    method: "Prior-year match",
                    confidence: "High",
                  },
                ],
                subtotal: (
                  <span className="flex items-center gap-[8px]">
                    Mapped 8,090,000 · interim TB line 8,400,000
                    <Pill variant="amber" size="sm">
                      off 310,000
                    </Pill>
                  </span>
                ),
              },
              { key: "cash", label: "Cash", open: false, rows: [] },
              { key: "ar", label: "Accounts receivable", open: false, rows: [] },
            ],
          }}
        />
      </Row>
    </Sheet>
  );
}
