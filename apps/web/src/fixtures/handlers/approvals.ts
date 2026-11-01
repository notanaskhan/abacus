// HOME-02's detail reads in fixture mode (I-01-T17; docs/contracts/review-grammar.md): the §754
// decision card and its citations, the Ridgeline section ladders and eligibility at Partner (L4),
// Samuel Ito's two agent outputs and the engagement team the detail names people from, served on
// the C3, C4 and C1 routes from seed/approvals-detail.ts. Decide answers the decided card (b); the
// screen never decides by itself (INV-1).

import type {
  AnalysisRequestOut,
  BulkSignOffIn,
  BulkSignOffOut,
  ListPageCitationV2Out,
} from "@abacus/api-client";
import { type FixtureHandler, type FixtureRequest, json } from "../../app-core/fixture-mode";
import {
  DECISION_754,
  DECISION_754_CITATIONS,
  DETAIL_TEAM,
  FELD_PROPOSAL,
  M2_FIX,
  SECTIONS,
  card754,
  card754Decided,
  feldProposal,
  m2Proposal,
} from "../seed/approvals-detail";
import { stableId } from "../seed/prng";

const NOT_FOUND = { detail: "not_found" };
const ANALYSIS_REQUEST = stableId("home02:analysis-request:754");

const section = (request: FixtureRequest) =>
  SECTIONS.find((s) => s.ladder.target.target_id === request.query.get("target_id"));

export interface ApprovalsDetailOptions {
  /** b: the card is already decided when the artboard opens. */
  decided?: boolean;
}

export function approvalsDetailHandlers(
  options: ApprovalsDetailOptions = {},
): Record<string, FixtureHandler> {
  let decided = options.decided === true;
  return {
    "GET /v1/decision-cards/{card_id}": ({ params }) =>
      params.card_id === DECISION_754
        ? json(decided ? card754Decided : card754)
        : json(NOT_FOUND, 404),
    "POST /v1/decision-cards/{card_id}/decide": ({ params }) => {
      if (params.card_id !== DECISION_754) return json(NOT_FOUND, 404);
      decided = true;
      return json(card754Decided);
    },
    "POST /v1/decision-cards/{card_id}/analysis-requests": ({ params }) =>
      params.card_id === DECISION_754
        ? json(
            {
              id: ANALYSIS_REQUEST,
              card_id: DECISION_754,
              requested_at: card754.card.requested_at,
              requested_by_user_id: card754.card.reserved_user_id ?? "",
            } satisfies AnalysisRequestOut,
            201,
          )
        : json(NOT_FOUND, 404),
    "GET /v1/citations": ({ query }) => {
      const items =
        query.get("anchor_type") === "decision_card" && query.get("anchor_id") === DECISION_754
          ? [...DECISION_754_CITATIONS]
          : [];
      return json({ items, total: items.length } satisfies ListPageCitationV2Out);
    },
    "GET /v1/sign-offs": (request) => {
      const found = section(request);
      return found === undefined ? json(NOT_FOUND, 404) : json(found.ladder);
    },
    // I-01-T19: SHL-12 f from HOME-02 e signs each eligible section on its own (R-SO-7).
    "POST /v1/sign-offs:bulk": ({ body }) => {
      const sent = body as BulkSignOffIn;
      const results = sent.targets.map((t): BulkSignOffOut["results"][number] => {
        const found = SECTIONS.find((s) => s.ladder.target.target_id === t.target_id);
        const ok = found?.eligibility.eligible === true;
        return {
          target_type: t.target_type,
          target_id: t.target_id,
          ok,
          sign_off_id: ok ? stableId(`home02:bulk:${t.target_id}`) : null,
          detail: ok ? null : ("incomplete" as const),
        };
      });
      const signed = results.filter((r) => r.ok).length;
      return json({
        results,
        signed,
        excluded: results.length - signed,
      } satisfies BulkSignOffOut);
    },
    "GET /v1/sign-offs/eligibility": (request) => {
      const found = section(request);
      return found === undefined ? json(NOT_FOUND, 404) : json(found.eligibility);
    },
    "GET /v1/proposals/{ref}": ({ params }) =>
      params.ref === FELD_PROPOSAL
        ? json(feldProposal)
        : params.ref === M2_FIX
          ? json(m2Proposal)
          : json(NOT_FOUND, 404),
    "GET /v1/engagements/{engagement_id}/team": () => json(DETAIL_TEAM),
  };
}
