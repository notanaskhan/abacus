// SHL-20 Evidence screening: one fixture scenario per artboard (docs/screens/SHL-20.md; P-06-T22),
// all seen by Cole Hart (Audit Staff) on the Granite Peak FY2026 SURL request:
//
//   a  Sat Sep 26, 10:14 AM: flagged, 29 of 31 answer, 2 flagged files with View and Return…
//   b  10:16 AM: a, with the screening-return draft to Luis Ferrante open (DV-1)
//   c  Mon Sep 28, 9:05 AM: the corrected files re-screening ("Screening 2 new files…")
//   d  Mon Sep 28, 9:05 AM: passed, 40 of 40 payments supported
//   e  Fri Sep 25: FRF-30418.pdf filed from the Inbox, not linked: not screened
//   f  a, with the thumbs-down "Why?" open
//
// The card, rerun, feedback, the return draft with its edit, send and Undo, the send-back with
// its reason catalogue, and the flags' citations and viewer documents ("View" → SHL-08). They live
// under fixtures/ (dev and test only); screens/SHL-20/scenarios.ts re-exports them.

import type {
  DecisionOut,
  FollowUpOut,
  ScreeningCardOut,
  ScreeningFeedbackIn,
  ScreeningFeedbackOut,
} from "@abacus/api-client";
import {
  type FixtureHandler,
  type Scenario,
  defineScenarios,
  json,
} from "../../app-core/fixture-mode";
import { trustHandlers } from "../handlers/trust";
import { seedScenario } from "../scenario";
import { getSeed } from "../seed";
import { stableId } from "../seed/prng";
import {
  CLOCK_DRAFT,
  CLOCK_FLAGGED,
  CLOCK_RERUN,
  CLOCK_UNLINKED,
  FLAGGED_CARD,
  FLAGGED_DOCUMENTS,
  GRANITE_PEAK,
  INVOICE_FLAG,
  LUIS_FERRANTE,
  PASSED_CARD,
  RUNNING_CARD,
  SEND_BACK_REASONS,
  STATEMENT_FLAG,
  SURL_ITEM,
  UNLINKED_FILE,
  screeningReturnDraft,
} from "../seed/screening";

const E0 = seedScenario();
const seed = getSeed();
const NOT_FOUND = { detail: "not found" };
const UNDO_MS = 10_000;

/** Luis Ferrante, the SURL request's client contact (the draft's recipient). */
const LUIS = seed.contacts[GRANITE_PEAK]?.find((c) => c.display_name === LUIS_FERRANTE)?.id ?? "";

export type Shl20State = "a" | "b" | "c" | "d" | "e" | "f";

/** What each artboard opens: the request's card, or (e) the unlinked file; and what it opens on. */
export interface Shl20Opens {
  subject: { engagementId: string; itemId: string } | null;
  open?: "feedback" | "follow-up";
  /** e: the file filed from the Inbox, not linked to a request. */
  file?: string;
}

export const OPENS: Readonly<Record<Shl20State, Shl20Opens>> = {
  a: { subject: { engagementId: GRANITE_PEAK, itemId: SURL_ITEM } },
  b: { subject: { engagementId: GRANITE_PEAK, itemId: SURL_ITEM }, open: "follow-up" },
  c: { subject: { engagementId: GRANITE_PEAK, itemId: SURL_ITEM } },
  d: { subject: { engagementId: GRANITE_PEAK, itemId: SURL_ITEM } },
  e: { subject: null, file: UNLINKED_FILE },
  f: { subject: { engagementId: GRANITE_PEAK, itemId: SURL_ITEM }, open: "feedback" },
};

/** The C5 v1.2 screening routes over one card that the person's writes change. */
export function screeningHandlers(
  initial: ScreeningCardOut,
  at: string,
): Record<string, FixtureHandler> {
  let card = initial;
  let draft: FollowUpOut | null = null;
  const path = "/v1/engagements/{engagement_id}/request-items/{item_id}";
  return {
    [`GET ${path}/screening`]: ({ params }) =>
      params.item_id === card.request_item_id ? json(card) : json(NOT_FOUND, 404),
    [`POST ${path}/screening/rerun`]: ({ params }) => {
      if (params.item_id !== card.request_item_id) return json(NOT_FOUND, 404);
      if (card.running) return json({ detail: "screening_running" }, 409);
      card = { ...card, running: true };
      return json({ request_item_id: card.request_item_id, running: true, as_of: at }, 202);
    },
    "POST /v1/screenings/{screening_result_id}/feedback": ({ params, body }) => {
      if (params.screening_result_id !== card.screening_result_id) return json(NOT_FOUND, 404);
      const asked = (body ?? {}) as ScreeningFeedbackIn;
      if (asked.thumb === "down" && (asked.reason_code ?? null) === null) {
        return json({ detail: "reason_required" }, 422);
      }
      const given: ScreeningFeedbackOut = {
        screening_result_id: card.screening_result_id,
        thumb: asked.thumb,
        reason_code: asked.reason_code ?? null,
        created_at: at,
      };
      card = { ...card, my_feedback: given };
      return json(given, 201);
    },
    [`POST ${path}/follow-ups`]: ({ params }) => {
      if (params.item_id !== card.request_item_id) return json(NOT_FOUND, 404);
      draft = screeningReturnDraft(LUIS, "Cole Hart");
      return json(draft, 201);
    },
    "PATCH /v1/follow-ups/{follow_up_id}": ({ params, body }) => {
      if (draft === null || params.follow_up_id !== draft.id) return json(NOT_FOUND, 404);
      if (draft.status !== "drafted") return json({ detail: "follow_up_already_sent" }, 409);
      const text = (body as { body?: string } | null)?.body?.trim() ?? "";
      if (text === "") return json({ detail: "invalid" }, 422);
      draft = { ...draft, body: text, edited: true };
      return json(draft);
    },
    "POST /v1/follow-ups/{follow_up_id}/send": ({ params }) => {
      if (draft === null || params.follow_up_id !== draft.id) return json(NOT_FOUND, 404);
      if (draft.status !== "drafted") return json({ detail: "follow_up_already_sent" }, 409);
      draft = {
        ...draft,
        status: "sent",
        sent_by: stableId("user:cole-hart"),
        sent_at: at,
        undo_until: new Date(Date.parse(at) + UNDO_MS).toISOString(),
      };
      return json(draft);
    },
    "POST /v1/follow-ups/{follow_up_id}/undo": ({ params }) => {
      if (draft === null || params.follow_up_id !== draft.id) return json(NOT_FOUND, 404);
      draft = { ...draft, status: "drafted", sent_by: null, sent_at: null, undo_until: null };
      return json(draft);
    },
    "GET /v1/engagements/{engagement_id}/review-reason-codes/{applies_to}": () =>
      json(SEND_BACK_REASONS),
    "POST /v1/engagements/{engagement_id}/evidence-versions/{version_id}/decision/send-back": ({
      params,
      body,
    }) => {
      const flag = card.file_flags.find((f) => f.evidence_version_id === params.version_id);
      if (flag === undefined) return json(NOT_FOUND, 404);
      const decision: DecisionOut = {
        id: `decision:${flag.evidence_version_id}`,
        decision: "send_back",
        evidence_version_id: flag.evidence_version_id,
        reason_code: (body as { reason_code?: string } | null)?.reason_code ?? null,
        item_status: "returned",
        request_item_ids: [card.request_item_id],
        corrects_proposal: false,
      };
      return json(decision, 201);
    },
  };
}

function scenario(state: Shl20State, clock: string, card: ScreeningCardOut): Scenario {
  return {
    state,
    persona: "cole-hart",
    clock,
    handlers: {
      ...E0.handlers,
      ...trustHandlers({
        citations: [STATEMENT_FLAG, INVOICE_FLAG].map((out) => ({
          anchor: { type: "request_item", id: SURL_ITEM, ref: "screening", section: null },
          out,
        })),
        documents: FLAGGED_DOCUMENTS,
      }),
      ...screeningHandlers(card, clock),
    },
  };
}

export const scenarios = defineScenarios({
  a: scenario("a", CLOCK_FLAGGED, FLAGGED_CARD),
  b: scenario("b", CLOCK_DRAFT, FLAGGED_CARD),
  c: scenario("c", CLOCK_RERUN, RUNNING_CARD),
  d: scenario("d", CLOCK_RERUN, PASSED_CARD),
  e: scenario("e", CLOCK_UNLINKED, FLAGGED_CARD),
  f: scenario("f", CLOCK_FLAGGED, FLAGGED_CARD),
});
