// SHL-15 a, a′ ("ap"), a″ ("app"), b, c, d, e (P-04-T54): one scenario per artboard from the C3
// stub-3 frames (seed/review.ts, P-04-T34) with what the sheet also reads (seed/issues-shl15.ts):
// Feld's four issues in the queue's order, their details, the teams and Northwind's contact. Each
// artboard names what it opens. `agents_off` is the fix sheet when no fix runner is registered
// (409 `fix_runner_unavailable`, P-04 F7).
import type { IssueCreateIn, IssueDetailOut } from "@abacus/api-client";
import { type Scenario, defineScenarios, json } from "../../app-core/fixture-mode";
import { reviewScenarios } from "../handlers/review";
import {
  BULK_IDS,
  BULK_TEXT,
  CREATED_B,
  CREATED_C,
  DRAFT_B,
  DRAFT_C,
  FELD_ENGAGEMENT,
  FELD_ISSUES,
  FELD_TEAM,
  FIX_18A_PROPOSAL,
  type IssueDraft,
  NORTHWIND_CONTACTS,
  NORTHWIND_ENGAGEMENT,
  NORTHWIND_TEAM,
  feldDetail,
  feldPage,
} from "../seed/issues-shl15";
import { FELD_1040, SHL15, issueRow, k1 } from "../seed/review";

export const STATES = ["a", "ap", "app", "b", "c", "d", "e", "agents_off"] as const;
export type Shl15State = (typeof STATES)[number];

const all = reviewScenarios("SHL-15");
const NOT_FOUND = { detail: "not_found" };

/** The sheet each artboard opens: fix instructions on an issue, a new issue, bulk, or d's block. */
export type Shl15Open =
  | { mode: "fix"; issueId: string }
  | {
      mode: "new";
      record: { type: string; id: string };
      engagementId: string;
      draft: IssueDraft;
      meta: string;
      context?: string;
    }
  | {
      mode: "bulk";
      record: { type: string; id: string };
      ids: readonly string[];
      text: string;
      meta: string;
    }
  | { mode: "explain"; issueId: string };

export const OPENS: Record<Shl15State, Shl15Open> = {
  a: { mode: "fix", issueId: issueRow.id },
  ap: { mode: "fix", issueId: issueRow.id },
  app: { mode: "fix", issueId: issueRow.id },
  agents_off: { mode: "fix", issueId: issueRow.id },
  b: {
    mode: "new",
    record: { type: DRAFT_B.create.record_type, id: DRAFT_B.create.record_id },
    engagementId: NORTHWIND_ENGAGEMENT,
    draft: DRAFT_B,
    meta: "EBP-04 · Northwind",
  },
  c: {
    mode: "new",
    record: { type: "tax_return", id: FELD_1040 },
    engagementId: FELD_ENGAGEMENT,
    draft: DRAFT_C,
    meta: "2025 Form 1040 · Feld",
    context: "Feld",
  },
  d: { mode: "explain", issueId: issueRow.id },
  e: {
    mode: "bulk",
    record: { type: "tax_return", id: FELD_1040 },
    ids: BULK_IDS,
    text: BULK_TEXT,
    meta: "2025 Form 1040 · Feld",
  },
};

/** The artboard's own detail for the 18A issue (a, a′, a″, d), the others from Feld's list. */
const DETAIL: Partial<Record<Shl15State, IssueDetailOut>> = {
  a: SHL15.a,
  ap: SHL15.a_prime,
  app: SHL15.a_double_prime,
  agents_off: SHL15.a,
  d: SHL15.d,
};

function scenario(state: Shl15State): Scenario {
  const base = all[state === "agents_off" ? "a" : state] as Scenario;
  const created: IssueDetailOut[] = [];
  return {
    ...base,
    state,
    handlers: {
      ...base.handlers,
      "GET /v1/issues": () => json(feldPage([...FELD_ISSUES, ...created.map((c) => c.issue)])),
      "GET /v1/issues/{issue_id}": ({ params }) => {
        const issueId = params.issue_id ?? "";
        const own = DETAIL[state];
        const found =
          own !== undefined && issueId === own.issue.id
            ? own
            : (created.find((c) => c.issue.id === issueId) ?? feldDetail(issueId));
        return found === undefined ? json(NOT_FOUND, 404) : json(found);
      },
      "POST /v1/issues": ({ body }) => {
        const sent = body as IssueCreateIn;
        const made = sent.kind === "review_point" ? CREATED_C : CREATED_B;
        created.push(made);
        return json(made, 201);
      },
      "POST /v1/issues/{issue_id}/send-to-client": () => json(SHL15.b),
      "GET /v1/proposals/{ref}": ({ params }) =>
        params.ref === k1.ref ? json(FIX_18A_PROPOSAL) : json(NOT_FOUND, 404),
      ...(state === "agents_off"
        ? {
            "POST /v1/issues/{issue_id}/fix-instructions": () =>
              json({ detail: "fix_runner_unavailable" }, 409),
          }
        : {}),
      "GET /v1/engagements/{engagement_id}/team": ({ params }) =>
        json(params.engagement_id === NORTHWIND_ENGAGEMENT ? NORTHWIND_TEAM : FELD_TEAM),
      "GET /v1/engagements/{engagement_id}/client-contacts": ({ params }) =>
        json(params.engagement_id === NORTHWIND_ENGAGEMENT ? NORTHWIND_CONTACTS : []),
    },
  };
}

export const scenarios = defineScenarios(
  Object.fromEntries(STATES.map((s) => [s, scenario(s)])) as Record<Shl15State, Scenario>,
);
