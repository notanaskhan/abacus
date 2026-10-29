// POR-06 Sign (N-02-T26): one scenario per artboard part 1 builds (docs/screens/POR-06.md), each a
// data condition on C7's portal routes for Owen Calder. a review (ERSD not accepted, Continue waits
// for page 3); b the sign step (ERSD accepted, the provider's view open); c the return after the
// provider completed (the server says signed: the completion card); `pending` the return before
// it has (never Completed); g declined (Withdraw decline); `restricted` a person who is not a signer
// (every read 404); `list` the Sign area's list.

import type { PortalEnvelopeView } from "@abacus/api-client";
import { type Scenario, defineScenarios } from "../../app-core/fixture-mode";
import { portalHandlers } from "../handlers/portal";
import { type PortalEnvelopeOptions, portalEnvelopeHandlers } from "../handlers/portal-envelopes";
import {
  E13_ID,
  E13_SESSION,
  E13_VIEW,
  POR06_CLOCK,
  POR06_PERSONA,
  POR06_SIGNED_CLOCK,
} from "../seed/portal-envelopes";

/** What an artboard opens: the list, an envelope, or the provider's return to it. */
export interface Por06Artboard {
  page: "list" | "envelope" | "return";
  envelopeId?: string;
  /** The return's `?session=` (the provider's one-time view). */
  session?: string;
}

const CONSENTED: PortalEnvelopeView = { ...E13_VIEW, esign_consent_needed: false };
const IN_PROVIDER: PortalEnvelopeView = { ...CONSENTED, signing_session: E13_SESSION };
const DECLINED: PortalEnvelopeView = {
  ...E13_VIEW,
  row: { ...E13_VIEW.row, status: "declined", my_status: "declined" },
  outcome: "declined",
};

const at = (state: string, options: PortalEnvelopeOptions, clock = POR06_CLOCK): Scenario => ({
  state,
  persona: POR06_PERSONA,
  clock,
  handlers: { ...portalHandlers({ clock }), ...portalEnvelopeHandlers(options) },
});

const BUILD = {
  a: () => at("a", {}),
  b: () => at("b", { view: IN_PROVIDER }),
  c: () => at("c", { view: IN_PROVIDER, signs: true }, POR06_SIGNED_CLOCK),
  pending: () => at("pending", { view: IN_PROVIDER }),
  g: () => at("g", { view: DECLINED }),
  restricted: () => at("restricted", { restricted: true }),
  list: () => at("list", {}),
} as const;

export type Por06State = keyof typeof BUILD;

export const scenarios = defineScenarios({
  a: BUILD.a(),
  b: BUILD.b(),
  c: BUILD.c(),
  pending: BUILD.pending(),
  g: BUILD.g(),
  restricted: BUILD.restricted(),
  list: BUILD.list(),
});

/** A scenario with handlers of its own (the writes change only its copy of the envelope). */
export function freshScenario(state: Por06State): Scenario {
  return BUILD[state]();
}

const ENVELOPE = { page: "envelope", envelopeId: E13_ID } as const;
const RETURN = { page: "return", envelopeId: E13_ID, session: E13_SESSION.session_id } as const;

export const ARTBOARD: Readonly<Record<Por06State, Por06Artboard>> = {
  a: ENVELOPE,
  b: ENVELOPE,
  c: RETURN,
  pending: RETURN,
  g: ENVELOPE,
  restricted: ENVELOPE,
  list: { page: "list" },
};
