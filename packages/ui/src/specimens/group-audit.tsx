import { type JSX, useState } from "react";
import { CoverageBar, type CoverageMeasure } from "../data/CoverageBar";
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
