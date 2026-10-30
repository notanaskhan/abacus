import { type JSX, useState } from "react";
import type { Actor } from "../attribution/actor";
import { ApprovalCard, type DiffRow } from "../gates/approval-card";
import { DecisionCard } from "../gates/decision-card";
import { SignOffSlots } from "../gates/sign-off-slots";
import { Row, Sheet } from "./frame";
import { NORTHWIND, NORTHWIND_FIGURES, STAFF } from "./seed-figures";

// E7 human gates (P-04-T40): the approval card, sign-off slots and decision card, seen by a
// person and by the agent. Northwind PY2025's contributions receivable (blueprint 01 §9.4) is the
// change approved; every gate verb renders through HumanAction, so the agent's view has none.

const HANNAH: Actor = { kind: "human", name: STAFF.hannah };
const AGENT: Actor = { kind: "agent" };

const CITED: DiffRow[] = [
  {
    key: "receivable",
    label: "Contributions receivable",
    before: null,
    after: NORTHWIND_FIGURES.contributionsReceivable,
    cites: 2,
  },
  {
    key: "net-assets",
    label: "Net assets available, Dec 31, 2025",
    before: NORTHWIND_FIGURES.netAssetsUnadjusted,
    after: NORTHWIND_FIGURES.netAssetsAvailable20251231,
    cites: 1,
  },
];

const UNCITED: DiffRow[] = CITED.map((r) => (r.key === "receivable" ? { ...r, cites: 0 } : r));

const SLOTS = [
  { level: "L1", role: "Preparer", signer: STAFF.samuel, at: "Sep 11, 4:02 PM" },
  { level: "L2", role: "Reviewer", signer: null, at: null },
  { level: "L3", role: "Partner", signer: null, at: null },
] as const;

export function GatesSpecimen(): JSX.Element {
  const [choice, setChoice] = useState<string | undefined>(undefined);
  return (
    <Sheet title="Human gates" meta={`${NORTHWIND} · PY2025`}>
      <Row name="Approval" spec="cited">
        <ApprovalCard
          title="Contributions receivable AJE"
          actor={HANNAH}
          rows={CITED}
          evidence={[{ key: "remit", label: "Contribution remittance report" }]}
          policyNote="Above the firm's AJE threshold: a reviewer approves."
          setLink={{ label: "Open the AJE set" }}
        />
      </Row>
      <Row name="Approval" spec="uncited blocks">
        <ApprovalCard title="Contributions receivable AJE" actor={HANNAH} rows={UNCITED} />
      </Row>
      <Row name="Approval" spec="agent view">
        <ApprovalCard title="Contributions receivable AJE" actor={AGENT} rows={CITED} />
      </Row>
      <Row name="Sign-offs" spec="C-25">
        <SignOffSlots
          slots={SLOTS}
          next="L2"
          actor={HANNAH}
          checks={[
            { key: "aje", label: "Every AJE approved", ok: true },
            { key: "notes", label: "Review notes cleared", ok: false, detail: "1 open" },
          ]}
        />
      </Row>
      <Row name="Decision" spec="inline">
        <DecisionCard
          title="Contributions receivable"
          reservedNote="Reserved to the engagement partner. The agent cannot decide."
          options={[
            { key: "book", label: "Book the receivable", recommended: true },
            { key: "disclose", label: "Disclose only" },
          ]}
          {...(choice === undefined ? {} : { value: choice })}
          onChange={setChoice}
          actor={HANNAH}
        />
      </Row>
    </Sheet>
  );
}
