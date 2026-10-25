import type { JSX } from "react";
import { AgentBlocks, AgentProse, type AgentBlocksPayload, type BlockFact } from "../agent/blocks";
import { Row, Sheet } from "./frame";
import { NORTHWIND_FIGURES } from "./seed-figures";

// P-09-T06: every AgentBlocks part, from code-registered facts: the seed's Northwind figures
// (seed-figures.ts), so the specimen matches the AUD-02 dock transcript.

const FACTS: Record<string, BlockFact> = {
  net_assets: { kind: "money", value: NORTHWIND_FIGURES.netAssetsUnadjusted },
  investments: { kind: "money", value: NORTHWIND_FIGURES.investmentsAtFairValue },
  notes: { kind: "money", value: NORTHWIND_FIGURES.participantNotes },
};

const ALL: AgentBlocksPayload = {
  parts: [
    {
      kind: "p",
      segments: [
        { kind: "text", text: "Trial Balance is complete and agreed to the net trust assets: " },
        { kind: "fact", fact_id: "net_assets" },
        { kind: "text", text: " (investments " },
        { kind: "fact", fact_id: "investments" },
        { kind: "text", text: " plus participant notes " },
        { kind: "fact", fact_id: "notes" },
        { kind: "text", text: ")" },
      ],
    },
    {
      kind: "table",
      head: ["Line", "Balance"],
      rows: [
        [
          { kind: "text", text: "Investments" },
          { kind: "fact", fact_id: "investments" },
        ],
        [
          { kind: "text", text: "Participant notes" },
          { kind: "fact", fact_id: "notes" },
        ],
      ],
    },
    { kind: "kv", rows: [{ label: "Read", value: [{ kind: "text", text: "Census workbook" }] }] },
    { kind: "metric", label: "Net trust assets", fact_id: "net_assets" },
    {
      kind: "file",
      artifact_id: "a1",
      name: "Harborline Net Trust Assets.pdf",
      meta: "Trustee certified report",
    },
    { kind: "badge", object: "engagement", code: "active" },
    { kind: "cite_list", cites: [{ kind: "cite", citation_id: "c1", n: 1 }] },
    {
      kind: "options",
      options: [
        { key: "run", title: "Run the plan", recommended: true },
        { key: "change", title: "Change the order", detail: "Reorder the levels first" },
      ],
    },
    { kind: "entity_ref", record_type: "workpaper", record_id: "w1" },
    { kind: "unknown_part" },
  ],
};

export function AgentBlocksSpecimen(): JSX.Element {
  return (
    <Sheet title="AgentBlocks" meta="v1 · nine parts · facts through format.ts · nodes only">
      <Row name="Every part" meaning="Validated on the server; an unknown kind is a neutral row">
        <div className="max-w-[330px]">
          <AgentBlocks blocks={ALL} facts={FACTS} />
        </div>
      </Row>
      <Row name="AgentProse" meaning="One paragraph of narration">
        <div className="max-w-[330px]">
          <AgentProse
            facts={FACTS}
            segments={[
              { kind: "text", text: "Investments at fair value are " },
              { kind: "fact", fact_id: "investments" },
            ]}
          />
        </div>
      </Row>
    </Sheet>
  );
}
