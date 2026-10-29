// SIG-02 a, e and f (N-02-T21): the envelope builder's C7 routes in fixture mode, one scenario per
// frame, seen by Grace Holloway at 9:40 AM. Send answers its Undo window (ADR-161) and Undo returns
// the draft; nothing here sends to a provider (INV-1: Send is the person's click).
import type { EnvelopeOut, SendOut, ValidationOut } from "@abacus/api-client";
import { FORM_PAGE_PNG } from "@abacus/ui/specimens";
import { type FixtureHandler, type Scenario, json } from "../../app-core/fixture-mode";
import { seedScenario } from "../scenario";
import {
  CHECKS,
  CHECKS_F,
  HARBORVIEW,
  HARBORVIEW_NO_EMAIL,
  POLICIES,
  RIDGELINE_LETTER,
  SIG02_CLOCK,
  SIG02_PERSONA,
} from "../seed/envelopes";

export const STATES = ["a", "e", "f"] as const;
export type Sig02State = (typeof STATES)[number];

function png(): Response {
  const base64 = FORM_PAGE_PNG.slice(FORM_PAGE_PNG.indexOf(",") + 1);
  const raw = atob(base64);
  const out = new Uint8Array(new ArrayBuffer(raw.length));
  for (let i = 0; i < raw.length; i += 1) out[i] = raw.charCodeAt(i);
  return new Response(out.buffer, {
    status: 200,
    headers: { "Content-Type": "image/png", "Cache-Control": "private, no-store" },
  });
}

export function envelopeHandlers(
  envelope: EnvelopeOut,
  checks: ValidationOut,
): Record<string, FixtureHandler> {
  const own = (params: Readonly<Record<string, string>>) =>
    params["envelope_id"] === envelope.row.id;
  const missing = json({ detail: "not_found" }, 404);
  return {
    "GET /v1/envelopes/{envelope_id}": ({ params }) => (own(params) ? json(envelope) : missing),
    "GET /v1/envelope-policies": () => json(POLICIES),
    "POST /v1/envelopes/{envelope_id}/validate": ({ params }) =>
      own(params) ? json(checks) : missing,
    "PUT /v1/envelopes/{envelope_id}": ({ params }) =>
      own(params) ? json({ ...envelope, version: envelope.version + 1 }) : missing,
    "POST /v1/envelopes/{envelope_id}/send": ({ params }) =>
      own(params)
        ? json({
            envelope_id: envelope.row.id,
            grant_id: "00000000-0000-4000-8000-0000000000e1",
            not_before: "2026-09-14T14:40:10Z",
          } satisfies SendOut)
        : missing,
    "POST /v1/envelopes/{envelope_id}/send/undo": ({ params }) =>
      own(params) ? json(envelope) : missing,
    "GET /v1/envelopes/{envelope_id}/documents/{document_id}/pages/{page_no}": ({ params }) =>
      own(params) ? png() : missing,
  };
}

const FRAMES: Record<Sig02State, { envelope: EnvelopeOut; checks: ValidationOut }> = {
  a: { envelope: HARBORVIEW, checks: CHECKS.a },
  e: { envelope: RIDGELINE_LETTER, checks: CHECKS.e },
  f: { envelope: HARBORVIEW_NO_EMAIL, checks: CHECKS_F },
};

/** The envelope each frame opens. */
export const OPENS: Record<Sig02State, string> = {
  a: HARBORVIEW.row.id,
  e: RIDGELINE_LETTER.row.id,
  f: HARBORVIEW_NO_EMAIL.row.id,
};

const e0 = seedScenario();

export const scenarios = Object.fromEntries(
  STATES.map((s) => [
    s,
    {
      ...e0,
      state: s,
      persona: SIG02_PERSONA,
      clock: SIG02_CLOCK,
      handlers: { ...e0.handlers, ...envelopeHandlers(FRAMES[s].envelope, FRAMES[s].checks) },
    } satisfies Scenario,
  ]),
) as Record<Sig02State, Scenario>;
