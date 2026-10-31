// POR-06 Sign (N-02-T26): one scenario per artboard part 1 builds (docs/screens/POR-06.md), each a
// data condition on C7's portal routes for Owen Calder. a review (ERSD not accepted, Continue waits
// for page 3); b the sign step (ERSD accepted, the provider's view open); c the return after the
// provider completed (the server says signed: the completion card); `pending` the return before
// it has (never Completed); g declined (Withdraw decline); `restricted` a person who is not a signer
// (every read 404); `list` the Sign area's list.
//
// N-02-T29: d Owen's Form 8879-PE (identity questions in the provider's view); e the Feld joint
// 8879 as Claire sees it after signing (Jonah signs with his own link); f Dana's representation
// letter before its date (the server holds signing until Oct 9); h DF-11, identity check failed.

import type { PortalEnvelopeView } from "@abacus/api-client";
import { type Scenario, defineScenarios } from "../../app-core/fixture-mode";
import { portalHandlers } from "../handlers/portal";
import { type PortalEnvelopeOptions, portalEnvelopeHandlers } from "../handlers/portal-envelopes";
import {
  E13_ID,
  E13_SESSION,
  E13_VIEW,
  E14_FAILED_VIEW,
  E14_ID,
  E14_VIEW,
  E15_ID,
  E15_VIEW,
  E16_ID,
  E16_VIEW,
  POR06_CLOCK,
  POR06_D_CLOCK,
  POR06_E_CLOCK,
  POR06_E_PERSONA,
  POR06_F_CLOCK,
  POR06_F_PERSONA,
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

const at = (
  state: string,
  options: PortalEnvelopeOptions,
  clock = POR06_CLOCK,
  persona = POR06_PERSONA,
): Scenario => ({
  state,
  persona,
  clock,
  handlers: { ...portalHandlers({ clock }), ...portalEnvelopeHandlers(options) },
});

const BUILD = {
  a: () => at("a", {}),
  b: () => at("b", { view: IN_PROVIDER }),
  c: () => at("c", { view: IN_PROVIDER, signs: true }, POR06_SIGNED_CLOCK),
  pending: () => at("pending", { view: IN_PROVIDER }),
  d: () => at("d", { view: E14_VIEW }, POR06_D_CLOCK),
  e: () => at("e", { view: E15_VIEW, signedRows: [] }, POR06_E_CLOCK, POR06_E_PERSONA),
  f: () => at("f", { view: E16_VIEW, signedRows: [] }, POR06_F_CLOCK, POR06_F_PERSONA),
  g: () => at("g", { view: DECLINED }),
  h: () => at("h", { view: E14_FAILED_VIEW }),
  restricted: () => at("restricted", { restricted: true }),
  list: () => at("list", {}),
} as const;

export type Por06State = keyof typeof BUILD;

export const scenarios = defineScenarios({
  a: BUILD.a(),
  b: BUILD.b(),
  c: BUILD.c(),
  pending: BUILD.pending(),
  d: BUILD.d(),
  e: BUILD.e(),
  f: BUILD.f(),
  g: BUILD.g(),
  h: BUILD.h(),
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
  d: { page: "envelope", envelopeId: E14_ID },
  e: { page: "envelope", envelopeId: E15_ID },
  f: { page: "envelope", envelopeId: E16_ID },
  g: ENVELOPE,
  h: { page: "envelope", envelopeId: E14_ID },
  restricted: ENVELOPE,
  list: { page: "list" },
};
