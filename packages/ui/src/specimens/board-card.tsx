// C-24 BoardCard, its Header and Lane, C-26 AgentProgress and the 280 navigator (F-08-T21;
// DEC-5929): every look, variant and overlay on Granite Peak's BH-FS-430 (TPL-21's seed names;
// figures are placeholders drawn from the specimen seed, never a consumer's data).
import { type JSX, useState } from "react";
import { AgentProgress, BoardCard, BoardColumnHeader, BoardLane, BoardNavigator } from "../board";
import { Row, Sheet } from "./frame";

const CARD = {
  title: "Search for unrecorded liabilities",
  code: "BH-FS-430",
  owner: "CH",
  ownerName: "Cole Hart",
  metrics: [3, 4, 1, 2] as const,
  p: { level: "L1", role: "Preparer", signer: "Cole Hart", at: "Sep 24, 9:30 AM" },
  r: { level: "L2", role: "Reviewer", signer: null, at: null },
};

export function BoardCardSpecimen(): JSX.Element {
  const [lane, setLane] = useState(false);
  const [nav, setNav] = useState(false);
  return (
    <Sheet title="BoardCard C-24" meta="262 · 196 · overlays without colour fills">
      <Row name="Looks" spec="rest · hover · selected · ghost">
        {(["rest", "hover", "selected", "ghost"] as const).map((look) => (
          <BoardCard key={look} {...CARD} look={look} agent={{ state: "progress", pct: 40 }} />
        ))}
      </Row>
      <Row name="Overlays" spec="Needs input · Waiting on client · Agent running · Sent back">
        <BoardCard {...CARD} flag="input" />
        <BoardCard {...CARD} flag="client" />
        <BoardCard {...CARD} spin agent={{ state: "running" }} />
        <BoardCard {...CARD} sentBy="Hannah Leclerc" p={{ ...CARD.p, stale: true }} />
      </Row>
      <Row name="Variants" spec="control (196) · return · close">
        <BoardCard
          {...CARD}
          variant="control"
          width={196}
          code="CC6.1"
          title="Logical access is reviewed quarterly"
          tag="CC6.1"
          result="none"
        />
        <BoardCard
          {...CARD}
          variant="return"
          title="Form 1120-S"
          sub="Copperleaf Coffee Roasters, Inc."
          pill="Ready"
          due="Due Mar 16"
        />
        <BoardCard
          {...CARD}
          variant="close"
          title="Bank reconciliations"
          done={{ text: "3 of 5", running: true }}
        />
      </Row>
      <Row name="AgentProgress C-26" spec="progress · running · input · client · done">
        <AgentProgress state="progress" pct={40} />
        <AgentProgress state="running" />
        <AgentProgress state="input" />
        <AgentProgress state="client" />
        <AgentProgress state="done" />
      </Row>
      <Row name="Header" spec="40 · disc · count">
        <BoardColumnHeader label="Not started" count={4} disc="todo" />
        <BoardColumnHeader label="In progress" count={5} disc="half" />
        <BoardColumnHeader label="In review" count={2} disc="dot" />
        <BoardColumnHeader label="Complete" count={2} disc="done" />
      </Row>
      <Row name="Lane" spec="34 · meta · DoneCount">
        <BoardLane
          title="Planning"
          meta="8 programs"
          done="8 of 8"
          collapsed={lane}
          onToggle={setLane}
        >
          <p className="p-[12px] text-[12px] text-ink-3">Lane body</p>
        </BoardLane>
      </Row>
      <Row name="Navigator" spec="280 · collapses to a 44 rail">
        <BoardNavigator
          title="Programs"
          collapsed={nav}
          onToggle={setNav}
          items={[
            { key: "planning", label: "Planning", count: 8 },
            { key: "fieldwork", label: "Fieldwork", count: 13 },
            { key: "area-a", label: "Area A · Revenue and receivables", count: 4, depth: 1 },
            { key: "area-b", label: "Area B · Purchases and payables", count: 5, depth: 1 },
          ]}
        />
      </Row>
    </Sheet>
  );
}
