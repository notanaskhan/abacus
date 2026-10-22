import { type JSX, useState } from "react";
import { AgentText } from "../agent-text";
import { type Actor, formatActor } from "../attribution/actor";
import { AgentFilledMarker, type Suggestion, adoptSuggestion } from "../attribution/agent-filled";
import { HumanAction } from "../attribution/human-action";
import { Held, Row, Sheet } from "./frame";

// Attribution and human verbs (F-05-T30): formatActor, HumanAction (renders for a person, nothing
// for the agent), AgentText, and the C-31 AgentFilledMarker states on the BH-FS-430 sheet sample.

const HANNAH: Actor = { kind: "human", name: "Hannah Leclerc" };
const AGENT: Actor = { kind: "agent" };
const CITES = ["Invoice FRF-30418 · Jun 29, 2026", "Payment · Jul 22, 2026"];

export function AttributionSpecimen(): JSX.Element {
  return (
    <Sheet title="Attribution" meta="formatActor is the only way to print an actor">
      <Row name="Person" spec="name">
        <span className="text-body">{formatActor(HANNAH)}</span>
      </Row>
      <Row name="Via the agent" spec="X via Agent">
        <span className="text-body">
          {formatActor({ kind: "agent_assisted", person: "Samuel Ito" })}
        </span>
      </Row>
      <Row name="Policy" spec="Policy: name vN">
        <span className="text-body">
          {formatActor({ kind: "policy", name: "BH AJE thresholds", version: 2 })}
        </span>
      </Row>
      <Row name="HumanAction" meaning="Renders for a named person; nothing for the agent">
        <Held name="person">
          <HumanAction verb="Approve" object="Document" actor={HANNAH} />
        </Held>
        <Held name="agent: not rendered">
          <span className="inline-flex min-h-[30px] min-w-[60px] items-center rounded-pill text-meta text-ink-3 inset-ring-[0.5px] inset-ring-hair px-3">
            <HumanAction verb="Approve" object="Document" actor={AGENT} />
            (nothing)
          </span>
        </Held>
      </Row>
      <Row name="AgentText" meaning="Model text, sanitised; text-para ink-2">
        <AgentText text="Invoice FRF-30418 for June freight was paid Jul 22 and recorded in July." />
      </Row>
    </Sheet>
  );
}

const ROWS: { n: number; vendor: string; s: Suggestion; exception?: boolean }[] = [
  {
    n: 1,
    vendor: "Front Range Freight Co.",
    s: { state: "suggested", value: "Improperly excluded", cites: CITES },
    exception: true,
  },
  {
    n: 27,
    vendor: "Basin Electric Cooperative",
    s: {
      state: "edited",
      value: "Properly excluded",
      was: "Properly included",
      by: HANNAH,
      at: "Oct 1",
    },
  },
  {
    n: 28,
    vendor: "Cobalt Uniform Supply",
    s: { state: "running", value: "", ask: "Conclusion · running" },
  },
  {
    n: 29,
    vendor: "Granite Rock Logistics",
    s: { state: "input", value: "", ask: "Which period does #40188 belong to?" },
  },
  { n: 30, vendor: "Peak Signage Co.", s: { state: "empty", value: "" } },
];

export function AgentFilledSpecimen(): JSX.Element {
  const [first, setFirst] = useState<Suggestion>(ROWS[0]?.s ?? { state: "empty", value: "" });
  return (
    <Sheet
      title="AgentFilledMarker (C-31)"
      meta="suggested · adopted · edited · running · input · empty"
    >
      {ROWS.map((r, i) => (
        <Row key={r.n} name={`${String(r.n)} · ${r.vendor}`}>
          <AgentFilledMarker
            suggestion={i === 0 ? first : r.s}
            viewer={HANNAH}
            exception={r.exception === true}
            onAdopt={() => {
              setFirst(adoptSuggestion(first, HANNAH, "Oct 1"));
            }}
          />
        </Row>
      ))}
    </Sheet>
  );
}
