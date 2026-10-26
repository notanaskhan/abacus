// CLI-07's acceptance routes over the acceptance seed (P-07-T46; docs/contracts/acceptance-
// independence.md, live since P-07-T35): the record, its engagement and team, the review picker's
// people, and the writes — manual checks, flags, send to partner, the risk-partner review, the
// decision and condition completion. Typed with the generated client; writes change this handler
// set's own copy. They refuse as the live routes do:
//
//   - a persona not on the engagement's team answers 404 (the record cannot be read; INV-3);
//   - `allowed_actions` follow the persona's team role: the engagement partner holds read, prepare,
//     request_review and decide; the manager and client service read and prepare; the named risk
//     partner also completes the review; an action the persona lacks answers 403;
//   - answers and manual checks after send answer 409 `acceptance_sent` (DEC-375); any edit after
//     the decision 409 `decision_locked`; send with a check open, or a decision in Draft, 409
//     `acceptance_not_ready`; a stale `seen_version` 409 `stale_version`;
//   - an empty rationale, or Accept with conditions without one, 422 `rationale_required`;
//   - `staleMfa` makes the decision answer 403 `mfa_required` (the shell's step-up).

import type {
  AcceptanceConditionOut,
  AcceptanceDecisionIn,
  AcceptanceFlagIn,
  AcceptanceFlagOut,
  AcceptanceRecordOut,
  CandidateOut,
  ManualCheckCompleteIn,
  ManualCheckOut,
  ManualCheckRequestIn,
  RiskPartnerReviewIn,
  RiskPartnerReviewOut,
  SendToPartnerIn,
  TeamRosterMemberOut,
} from "@abacus/api-client";
import { type FixtureHandler, type FixtureRequest, json } from "../../app-core/fixture-mode";
import { DEFAULT_PERSONA } from "../handlers";
import type { EngagementRecordFixture } from "../seed/engagement-records";
import { slugOf } from "../seed/people";
import { stableId } from "../seed/prng";

const NOT_FOUND = { detail: "not_found" };
const FORBIDDEN = { detail: "forbidden" };

export interface AcceptanceFixture {
  engagement: EngagementRecordFixture;
  record: AcceptanceRecordOut;
  /** Who "Request risk-partner review…" offers (`GET …/team/candidates`). */
  candidates?: CandidateOut[];
}

export interface AcceptanceOptions {
  /** The handlers' clock (ISO 8601): when a write happens. */
  now: string;
  /** The decision answers 403 `mfa_required`. */
  staleMfa?: boolean;
}

const EP_ACTIONS = [
  "acceptance.read",
  "acceptance.prepare",
  "acceptance.request_review",
  "acceptance.decide",
];
const PREPARER_ACTIONS = ["acceptance.read", "acceptance.prepare"];

/** What each team role may do here, as the matrix grants it (engagements.yaml). */
const ACTIONS_BY_ROLE: Partial<Record<TeamRosterMemberOut["role"], string[]>> = {
  engagement_partner: EP_ACTIONS,
  manager: PREPARER_ACTIONS,
  client_service: PREPARER_ACTIONS,
};

function actionsOf(role: TeamRosterMemberOut["role"] | undefined): string[] {
  if (role === undefined) return [];
  return ACTIONS_BY_ROLE[role] ?? ["acceptance.read"];
}

const refuse = (detail: string, status: number, facts?: Record<string, unknown>): Response =>
  json(facts === undefined ? { detail } : { detail, facts }, status);

export function acceptanceHandlers(
  fixtures: readonly AcceptanceFixture[],
  options: AcceptanceOptions,
): Record<string, FixtureHandler> {
  const byId = new Map(fixtures.map((f) => [f.engagement.record.id, structuredClone(f)]));
  const team = (f: AcceptanceFixture): TeamRosterMemberOut[] => f.engagement.team ?? [];
  const memberOf = (f: AcceptanceFixture, request: FixtureRequest) => {
    const who = request.persona ?? DEFAULT_PERSONA;
    return team(f).find((m) => slugOf(m.display_name) === who);
  };
  const find = (request: FixtureRequest) => {
    const f = byId.get(request.params.engagement_id ?? "");
    if (f === undefined) return undefined;
    const me = memberOf(f, request);
    const reviewer =
      f.record.risk_partner_review != null &&
      (f.candidates ?? []).some(
        (c) =>
          c.user_id === f.record.risk_partner_review?.partner_id &&
          slugOf(c.display_name) === (request.persona ?? DEFAULT_PERSONA),
      );
    if (me === undefined && !reviewer) return undefined;
    const actions = [
      ...actionsOf(me?.role),
      ...(reviewer ? ["acceptance.read", "acceptance.complete_review"] : []),
    ];
    return { f, me, actions };
  };
  const view = (f: AcceptanceFixture, actions: string[]): AcceptanceRecordOut => ({
    ...f.record,
    allowed_actions: [...new Set(actions)],
  });
  const bump = (f: AcceptanceFixture): void => {
    f.record.version += 1;
  };
  const locked = (f: AcceptanceFixture): boolean =>
    f.record.status === "decided" || f.record.status === "declined";

  type Found = NonNullable<ReturnType<typeof find>>;
  const write =
    (action: string, apply: (found: Found, request: FixtureRequest) => Response) =>
    (request: FixtureRequest): Response => {
      const found = find(request);
      if (found === undefined) return json(NOT_FOUND, 404);
      if (!found.actions.includes(action)) return json(FORBIDDEN, 403);
      return apply(found, request);
    };
  const draftOnly = (f: AcceptanceFixture): Response | null => {
    if (locked(f)) return refuse("decision_locked", 409);
    if (f.record.status !== "draft") return refuse("acceptance_sent", 409);
    return null;
  };
  const openChecks = (f: AcceptanceFixture) =>
    (f.record.sections ?? []).filter((s) => s.answer_state === "manual_check_open");

  return {
    "GET /v1/engagements/{engagement_id}/record": (request) => {
      const found = find(request);
      return found === undefined ? json(NOT_FOUND, 404) : json(found.f.engagement.record);
    },
    "GET /v1/engagements/{engagement_id}/team": (request) => {
      const found = find(request);
      return found === undefined ? json(NOT_FOUND, 404) : json(team(found.f));
    },
    "GET /v1/engagements/{engagement_id}/team/candidates": (request) => {
      const found = find(request);
      return found === undefined ? json(NOT_FOUND, 404) : json(found.f.candidates ?? []);
    },
    "GET /v1/engagements/{engagement_id}/acceptance": (request) => {
      const found = find(request);
      return found === undefined ? json(NOT_FOUND, 404) : json(view(found.f, found.actions));
    },
    "POST /v1/engagements/{engagement_id}/acceptance/manual-checks/{section_code}/request": write(
      "acceptance.prepare",
      ({ f, me }, request) => {
        const stop = draftOnly(f);
        if (stop !== null) return stop;
        const section = (f.record.sections ?? []).find(
          (s) => s.code === request.params.section_code,
        );
        if (section === undefined) return json(NOT_FOUND, 404);
        const { requested_of } = request.body as ManualCheckRequestIn;
        const asked = team(f).find((m) => m.user_id === requested_of);
        if (
          asked === undefined ||
          actionsOf(asked.role).every((a) => a !== "acceptance.prepare") ||
          section.answer_state === "manual_check_open"
        ) {
          return refuse("invalid", 422, { field: "requested_of" });
        }
        const check: ManualCheckOut = {
          section_code: section.code,
          requested_of,
          requested_by: me?.user_id ?? "",
          requested_at: options.now,
          completed_at: null,
          completed_by: null,
          note: null,
        };
        section.manual_check = check;
        section.answer_state = "manual_check_open";
        bump(f);
        return json(check, 201);
      },
    ),
    "POST /v1/engagements/{engagement_id}/acceptance/manual-checks/{section_code}/complete": write(
      "acceptance.prepare",
      ({ f, me }, request) => {
        const stop = draftOnly(f);
        if (stop !== null) return stop;
        const section = (f.record.sections ?? []).find(
          (s) => s.code === request.params.section_code,
        );
        const check = section?.manual_check;
        if (section === undefined || check == null || check.completed_at != null) {
          return json(NOT_FOUND, 404);
        }
        if (check.requested_of !== me?.user_id) return json(FORBIDDEN, 403);
        const { note } = (request.body ?? {}) as ManualCheckCompleteIn;
        const done: ManualCheckOut = {
          ...check,
          completed_at: options.now,
          completed_by: me.user_id,
          note: note ?? null,
        };
        section.manual_check = done;
        section.answer_state = "manual_check_done";
        bump(f);
        return json(done);
      },
    ),
    "POST /v1/engagements/{engagement_id}/acceptance/flags": write(
      "acceptance.prepare",
      ({ f, me }, request) => {
        if (locked(f)) return refuse("decision_locked", 409);
        const body = request.body as AcceptanceFlagIn;
        const flag: AcceptanceFlagOut = {
          id: stableId(`acceptance-flag:added:${String(f.record.flags?.length ?? 0)}`),
          title: body.title,
          severity: body.severity,
          body: body.body,
          sources: body.sources ?? [],
          authored_by: me?.user_id ?? "",
          authored_at: options.now,
        };
        f.record.flags = [...(f.record.flags ?? []), flag];
        bump(f);
        return json(flag, 201);
      },
    ),
    "POST /v1/engagements/{engagement_id}/acceptance/send-to-partner": write(
      "acceptance.prepare",
      ({ f, me }, request) => {
        if (locked(f)) return refuse("decision_locked", 409);
        const { seen_version } = request.body as SendToPartnerIn;
        if (seen_version !== f.record.version) return refuse("stale_version", 409);
        if (f.record.status !== "draft") return refuse("illegal_transition", 409);
        const open = openChecks(f);
        if (open.length > 0) {
          return refuse("acceptance_not_ready", 409, {
            section: open[0]?.code,
            open_checks: open.length,
          });
        }
        f.record.status = "awaiting_partner";
        f.record.sent_to_partner_at = options.now;
        f.record.sent_to_partner_by = me?.user_id ?? null;
        bump(f);
        return json(f.record);
      },
    ),
    "POST /v1/engagements/{engagement_id}/acceptance/risk-partner-review": write(
      "acceptance.request_review",
      ({ f, me }, request) => {
        if (locked(f)) return refuse("decision_locked", 409);
        const { partner_id } = request.body as RiskPartnerReviewIn;
        const ok =
          (f.candidates ?? []).some((c) => c.user_id === partner_id) &&
          !team(f).some(
            (m) => m.user_id === partner_id && actionsOf(m.role).includes("acceptance.decide"),
          );
        if (!ok) return refuse("invalid", 422, { field: "partner_id" });
        const review: RiskPartnerReviewOut = {
          partner_id,
          requested_by: me?.user_id ?? "",
          requested_at: options.now,
          completed_at: null,
        };
        f.record.risk_partner_review = review;
        bump(f);
        return json(review, 201);
      },
    ),
    "POST /v1/engagements/{engagement_id}/acceptance/risk-partner-review/complete": write(
      "acceptance.complete_review",
      ({ f }) => {
        const review = f.record.risk_partner_review;
        if (review == null) return json(NOT_FOUND, 404);
        const done: RiskPartnerReviewOut = { ...review, completed_at: options.now };
        f.record.risk_partner_review = done;
        bump(f);
        return json(done);
      },
    ),
    "POST /v1/engagements/{engagement_id}/acceptance/decision": write(
      "acceptance.decide",
      ({ f, me }, request) => {
        if (options.staleMfa === true) {
          return refuse("forbidden", 403, { reason: "mfa_required" });
        }
        if (locked(f)) return refuse("decision_locked", 409);
        if (f.record.status !== "awaiting_partner") {
          return refuse("acceptance_not_ready", 409, { open_checks: openChecks(f).length });
        }
        const body = request.body as AcceptanceDecisionIn;
        if (body.seen_version !== f.record.version) return refuse("stale_version", 409);
        if (body.rationale.trim() === "") {
          return refuse("rationale_required", 422, { field: "rationale" });
        }
        const conditions = body.conditions ?? [];
        if (body.option === "accept_with_conditions" && conditions.length === 0) {
          return refuse("rationale_required", 422, { field: "conditions" });
        }
        if (body.option !== "accept_with_conditions" && conditions.length > 0) {
          return refuse("invalid", 422, { field: "conditions" });
        }
        if (
          f.record.risk_rating === "high" &&
          f.record.risk_partner_review?.completed_at == null
        ) {
          return refuse("review_required", 409);
        }
        f.record.decision = {
          option: body.option,
          rationale: body.rationale,
          decided_by: me?.user_id ?? "",
          decided_at: options.now,
        };
        f.record.conditions = conditions.map((c, i): AcceptanceConditionOut => ({
          id: stableId(`acceptance-condition:${f.record.id}:${String(i + 1)}`),
          text: c.text,
          assignee_user_id: c.assignee_user_id,
          due_on: c.due_on ?? null,
          completed_at: null,
          completed_by: null,
        }));
        f.record.status = body.option === "decline" ? "declined" : "decided";
        f.engagement.record = {
          ...f.engagement.record,
          status: body.option === "decline" ? "declined" : "accepted",
        };
        bump(f);
        return json(f.record, 201);
      },
    ),
    "POST /v1/engagements/{engagement_id}/acceptance/conditions/{condition_id}/complete": write(
      "acceptance.prepare",
      ({ f, me }, request) => {
        const condition = (f.record.conditions ?? []).find(
          (c) => c.id === request.params.condition_id,
        );
        if (condition === undefined) return json(NOT_FOUND, 404);
        if (condition.completed_at != null) {
          return refuse("invalid", 422, { condition_id: condition.id });
        }
        condition.completed_at = options.now;
        condition.completed_by = me?.user_id ?? null;
        return json(condition);
      },
    ),
  };
}
