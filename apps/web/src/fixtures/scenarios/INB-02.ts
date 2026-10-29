// INB-02 · Attachment triage & File-to: one fixture scenario per artboard (N-01-T15;
// docs/screens/INB-02.md), at E0 9:25 AM CT, seen by Grace Holloway. Over INB-01's handlers, the
// triage bundle of the artboard's message and an Apply that answers what it was sent (counts and
// the preparer notified; no undo grant until "Tell the client" sends, DEC-1061).
import type { TriageApplyIn, TriageApplyOut } from "@abacus/api-client";
import {
  type FixtureHandler,
  type Scenario,
  defineScenarios,
  json,
} from "../../app-core/fixture-mode";
import { meHandlers } from "../handlers";
import { inboxHandlers } from "../handlers/inbox";
import { type Inb02State, triageOf } from "../seed/inbox-triage";
import { stableId } from "../seed/prng";

export const INB02_PERSONA = "grace-holloway";
export const INB02_CLOCK = "2026-09-14T09:25:00-05:00";
const KEVIN = stableId("person:kevin-osei");

function handlers(state: Inb02State): Record<string, FixtureHandler> {
  const message = triageOf(state);
  return {
    ...meHandlers(),
    ...inboxHandlers(state === "f"),
    "GET /v1/inbox/messages/{message_id}/triage": () => json(message.bundle),
    "POST /v1/inbox/messages/{message_id}/triage/apply": ({ body }) => {
      const given = body as TriageApplyIn;
      const count = (d: string): number => given.decisions.filter((x) => x.decision === d).length;
      const out: TriageApplyOut = {
        filed: count("file"),
        ignored: count("ignore"),
        held: count("hold"),
        notified_user_ids: count("file") > 0 ? [KEVIN] : [],
        undo_grant_id: null,
      };
      return json(out);
    },
    "GET /v1/destinations": () => json([]),
  };
}

const base = (state: Inb02State): Scenario => ({
  state,
  persona: INB02_PERSONA,
  clock: INB02_CLOCK,
  handlers: handlers(state),
});

export const scenarios = defineScenarios({
  a: base("a"),
  a2: base("a2"),
  b: base("b"),
  c: base("c"),
  d: base("d"),
  e: base("e"),
  f: base("f"),
  g: base("g"),
});

/** The message an artboard's sheet opens, with its subject and sender. */
export function messageOf(state: Inb02State): { id: string; subject: string; sender: string } {
  const m = triageOf(state);
  return { id: m.bundle.message_id, subject: m.subject, sender: m.sender };
}
