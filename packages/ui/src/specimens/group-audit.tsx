import { type JSX, useState } from "react";
import { ConsolidationWorksheet } from "../data/ConsolidationWorksheet";
import { CoverageBar, type CoverageMeasure } from "../data/CoverageBar";
import { EliminationCard } from "../data/EliminationCard";
import { type EntityNode, EntityTree } from "../data/EntityTree";
import { type Milestone, MilestoneTimeline } from "../data/MilestoneTimeline";
import { Row, Sheet } from "./frame";

// The A-09 L2 kits (A-09-T08) on Harlow & Pike's FY2026 group (the handoff's AUD-32, AUD-34 and
// AUD-35 figures): the five-entity, three-tier structure; the Pruett & Lang milestones; the
// coverage bars. Kit sample data is never ported.

const STRUCTURE: EntityNode[] = [
  { id: "holdings", name: "Harlow & Pike Holdings, Inc.", level: 1, meta: "100% · Chicago" },
  { id: "operating", name: "Harlow & Pike Operating Co.", level: 2, meta: "100% · Chicago" },
  {
    id: "manufacturing",
    name: "Harlow & Pike Manufacturing, Inc.",
    level: 3,
    meta: "100% · Rockford",
  },
  {
    id: "distribution",
    name: "Harlow & Pike Distribution, Inc.",
    level: 3,
    meta: "100% · Denver",
  },
  { id: "real_estate", name: "Harlow & Pike Real Estate, LLC", level: 2, meta: "100% · Chicago" },
];

const MILESTONES: Milestone[] = [
  { key: "instructions", label: "Instructions acknowledged", due: "Sep 23", state: "done" },
  { key: "interim", label: "Interim memo", due: "Nov 30", state: "late", note: "Late · 1 day" },
  { key: "clearance", label: "Clearance letter", due: "Feb 12", state: "upcoming" },
  {
    key: "summary",
    label: "Summary of uncorrected misstatements",
    due: "Feb 12",
    state: "upcoming",
  },
];

const COVERAGE: CoverageMeasure[] = [
  {
    key: "third_party_sales",
    label: "Third-party sales",
    total: "73,000,000",
    segments: [
      { key: "full_scope", label: "Full scope", pct: 100, amount: "73,000,000" },
      { key: "specific_procedures", label: "Specific procedures", pct: 0, amount: "—" },
      { key: "rest", label: "Analytical only", pct: 0, amount: "—" },
    ],
  },
  {
    key: "total_assets",
    label: "Total assets",
    total: "50,760,000",
    segments: [
      { key: "full_scope", label: "Full scope", pct: 78, amount: "39,760,000" },
      { key: "specific_procedures", label: "Specific procedures", pct: 22, amount: "11,000,000" },
      { key: "rest", label: "Analytical only", pct: 0, amount: "—" },
    ],
  },
];

export function EntityTreeSpecimen(): JSX.Element {
  const [nodes, setNodes] = useState(STRUCTURE);
  return (
    <Sheet title="EntityTree" meta="treegrid · aria-level · Alt+Arrows move, indent, outdent">
      <Row name="Editable (AUD-32 c)" meaning="Three tiers at most; one root; ownership is a fact">
        <EntityTree label="Harlow & Pike structure" nodes={nodes} onChange={setNodes} />
      </Row>
      <Row name="Read only (AUD-32 d)" meaning="No handles, no moves">
        <EntityTree label="Harlow & Pike structure, finalized" nodes={STRUCTURE} />
      </Row>
    </Sheet>
  );
}

export function MilestoneTimelineSpecimen(): JSX.Element {
  return (
    <Sheet title="MilestoneTimeline" meta="done · late · upcoming; Late is the server's">
      <Row name="Pruett & Lang (AUD-35 d)" meaning="Late reads in text, never colour alone">
        <MilestoneTimeline label="Pruett & Lang milestones" milestones={MILESTONES} />
      </Row>
    </Sheet>
  );
}

export function CoverageBarSpecimen(): JSX.Element {
  return (
    <Sheet title="CoverageBar" meta="two stacked bars · View as table">
      <Row
        name="Coverage (AUD-34 e)"
        meaning="After eliminations by entity attribution; 78%, never 83%"
      >
        <CoverageBar label="Harlow & Pike coverage" measures={COVERAGE} />
      </Row>
    </Sheet>
  );
}

// The A-09-T15 C-38 kits on Harlow & Pike's AUD-33 a figures (three rows and E3, E4).
const WORDS = {
  level: (n: number) => `Level ${String(n)}`,
  status: { proposed: "Proposed", approved: "Approved", posted: "Posted", rejected: "Rejected" },
  approve: "Approve",
  edit: "Edit",
  reject: "Reject…",
  dr: "Dr",
  cr: "Cr",
  off: (amount: string) => `Off ${amount}`,
};

export function ConsolidationWorksheetSpecimen(): JSX.Element {
  const cols = [
    { key: "manufacturing", header: "Manufacturing" },
    { key: "distribution", header: "Distribution" },
    { key: "eliminations", header: "Eliminations" },
    { key: "consolidated", header: "Consolidated" },
  ];
  const rows = [
    {
      caption: "Intercompany receivable",
      section: "assets",
      cells: [
        { column: "manufacturing", amount: "2400000.00" },
        { column: "distribution", amount: "0.00" },
        { column: "eliminations", amount: "-2400000.00", codes: ["E4"] },
        { column: "consolidated", amount: "0.00" },
      ],
    },
    {
      caption: "Inventory",
      section: "assets",
      cells: [
        { column: "manufacturing", amount: "9600000.00" },
        { column: "distribution", amount: "6300000.00" },
        { column: "eliminations", amount: "-240000.00", codes: ["E3"] },
        { column: "consolidated", amount: "15660000.00" },
      ],
    },
    {
      caption: "Cost of goods sold",
      section: "income",
      cells: [
        { column: "manufacturing", amount: "45600000.00" },
        { column: "distribution", amount: "24800000.00" },
        { column: "eliminations", amount: "-17760000.00", codes: ["E2", "E3"] },
        { column: "consolidated", amount: "52640000.00" },
      ],
    },
  ]; // fmt: skip
  return (
    <Sheet
      title="ConsolidationWorksheet (C-38)"
      meta="statement grammar · tags light their cells · nothing summed"
    >
      <Row name="Posted" meaning="Credits in parentheses, nil as a dash">
        <ConsolidationWorksheet
          label="Consolidated"
          columns={cols}
          sections={{ assets: "Assets", income: "Income statement · 8 months" }}
          rows={rows}
        />
      </Row>
      <Row name="Proposed" meaning="Eliminations and consolidated in ink-2">
        <ConsolidationWorksheet
          label="Consolidated · proposed"
          columns={cols}
          sections={{ assets: "Assets" }}
          rows={rows.slice(0, 2)}
          pending
        />
      </Row>
    </Sheet>
  );
}

export function EliminationCardSpecimen(): JSX.Element {
  const [open, setOpen] = useState(true);
  const e3 = [
    { caption: "Cost of goods sold", debit: "240000.00", credit: "0.00" },
    { caption: "Inventory — Distribution", debit: "0.00", credit: "240000.00" },
  ];
  return (
    <Sheet title="EliminationCard (C-38)" meta="posted · proposed · off">
      <Row name="Posted, expanded">
        <div className="w-[396px]">
          <EliminationCard
            code="E3"
            level={2}
            description="Unrealized profit in Distribution's ending inventory"
            amount="240000.00"
            status="posted"
            lines={e3}
            expanded={open}
            selected
            onToggle={() => {
              setOpen((v) => !v);
            }}
            words={WORDS}
            computation="1,000,000 of Distribution's 8/31 inventory was bought from Manufacturing × Manufacturing's 2026 gross margin 24.0% (14,400,000 ÷ 60,000,000) = 240,000"
            citations={[
              "Distribution inventory by vendor 8-31-2026.xlsx",
              "Manufacturing TB 8/31",
            ]}
            provenance="Proposed by Accrued Agent 1:31 PM · Approved by Omar Haddad 1:58 PM · Posted 2:01 PM"
          />
        </div>
      </Row>
      <Row name="Proposed">
        <div className="w-[396px]">
          <EliminationCard
            code="E4"
            level={2}
            description="Intercompany balances"
            amount="2400000.00"
            status="proposed"
            lines={[]}
            words={WORDS}
            onApprove={() => undefined}
            subline="Manufacturing due from Distribution 2,400,000 = Distribution due to Manufacturing 2,400,000 ✓"
          />
        </div>
      </Row>
      <Row name="Off">
        <div className="w-[396px]">
          <EliminationCard
            code="E3"
            level={2}
            description="Unrealized profit in Distribution's ending inventory"
            amount="240000.00"
            status="proposed"
            lines={e3}
            words={WORDS}
            offBy="10000.00"
            onApprove={() => undefined}
          />
        </div>
      </Row>
    </Sheet>
  );
}
