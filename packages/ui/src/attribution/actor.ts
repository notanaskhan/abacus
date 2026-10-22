// Attribution (F-05-T30; plan 04 rule 9 and lint L6; F-05 H1). `formatActor` is the only way to
// print who did something: a person by name, an agent-assisted change as "Hannah Leclerc via
// Agent", a policy as "Policy: BH AJE thresholds v2". The Accrued Agent alone may suggest, draft
// and run, never decide, so no approval or sign-off ever reads "by Accrued Agent" (INV-5).

import { viaAgent } from "../format";

export type Actor =
  | { kind: "human"; name: string }
  /** The Accrued Agent on its own: suggestions, drafts, runs. */
  | { kind: "agent" }
  /** A person's change the agent helped with. */
  | { kind: "agent_assisted"; person: string }
  | { kind: "policy"; name: string; version: number }
  | { kind: "system" };

export const AGENT_NAME = "Accrued Agent";

export function formatActor(actor: Actor): string {
  switch (actor.kind) {
    case "human":
      return actor.name.trim();
    case "agent":
      return AGENT_NAME;
    case "agent_assisted":
      return viaAgent(actor.person);
    case "policy":
      return `Policy: ${actor.name.trim()} v${String(actor.version)}`;
    case "system":
      return "System";
  }
}

/** Only a named person may take a human-only action (INV-1). */
export function isPerson(actor: Actor): actor is { kind: "human"; name: string } {
  return actor.kind === "human";
}

/** The verbs only a person may perform (plan 04 rule 9; F-05 H1 adds Adopt). */
export const HUMAN_VERBS = [
  "Approve",
  "Sign off",
  "Release",
  "Send",
  "Post",
  "Decide",
  "Adopt",
] as const;
export type HumanVerb = (typeof HUMAN_VERBS)[number];

/**
 * An audit-trail actor from the API (`actor_kind`, `actor_name`): `human`, `agent`, `system`,
 * `support`. An agent row with a person's name is that person's change via the agent.
 */
export function actorFromAudit(kind: string, name: string | null): Actor {
  if (kind === "human") return { kind: "human", name: name ?? "Unknown person" };
  if (kind === "agent") {
    return name !== null && name !== AGENT_NAME
      ? { kind: "agent_assisted", person: name }
      : { kind: "agent" };
  }
  if (kind === "support" && name !== null) return { kind: "human", name };
  return { kind: "system" };
}
