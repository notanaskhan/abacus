// ENG-05's team routes over the team-roles seed (P-07-T39; DEC-327): the roster, the team
// approval, the add candidates, the EQR candidates, and the writes a manager makes on the Team tab
// (add, change role or hours, remove, the portal flag, confirmation reminders, replace the EQR).
// Typed with the generated client. Writes change this handler set's own copy. A walled or unknown
// engagement answers 404 (INV-3); a write the record's `allowed_actions` lacks answers 403; adding
// someone already on the team or making a team member EQR answers 409 as the live routes do.

import type {
  AbacusModulesEngagementsAcceptanceContractEqrOut,
  CandidateOut,
  EqrCandidateOut,
  EqrIn,
  PortalVisibilityIn,
  PortalVisibilityOut,
  RemindersIn,
  RemindersOut,
  TeamApprovalOut,
  TeamMemberIn,
  TeamRoleIn,
  TeamRosterMemberOut,
} from "@abacus/api-client";
import { type FixtureHandler, type FixtureRequest, json } from "../../app-core/fixture-mode";
import { DEFAULT_PERSONA } from "../handlers";
import type { Seed } from "../seed";
import type { EngagementRecordFixture } from "../seed/engagement-records";
import { DEMO_INSTANT } from "../seed/clock";

const NOT_FOUND = { detail: "not_found" };

/** The EQR's row on the roster (DEC-327): set only through `POST …/eqr`. */
const EQR: TeamRosterMemberOut["role"] = "eqr_reviewer";
const isEqr = (m: TeamRosterMemberOut): boolean => m.role === EQR;

export interface TeamFixture {
  record: EngagementRecordFixture;
  roster: TeamRosterMemberOut[];
  approval: TeamApprovalOut;
  candidates: CandidateOut[];
  eqr: EqrCandidateOut[];
}

export interface TeamSeen {
  reminders: string[];
}

export function teamRoleHandlers(
  seed: Seed,
  teams: readonly TeamFixture[],
  options: { now?: string; seen?: TeamSeen } = {},
): Record<string, FixtureHandler> {
  const byId = new Map(teams.map((t) => [t.record.record.id, structuredClone(t)]));
  const now = options.now ?? DEMO_INSTANT;
  const find = (request: FixtureRequest): TeamFixture | undefined => {
    const found = byId.get(request.params.engagement_id ?? "");
    if (found === undefined) return undefined;
    const who = request.persona ?? DEFAULT_PERSONA;
    const walled = seed.walls.some(
      (w) => w.personSlug === who && w.clientId === found.record.record.client_id,
    );
    return walled ? undefined : found;
  };
  const may = (t: TeamFixture, action: string): boolean =>
    (t.record.record.allowed_actions ?? []).includes(action);
  const write =
    (action: string, apply: (t: TeamFixture, request: FixtureRequest) => Response) =>
    (request: FixtureRequest): Response => {
      const t = find(request);
      if (t === undefined) return json(NOT_FOUND, 404);
      if (!may(t, action)) return json({ detail: "forbidden" }, 403);
      return apply(t, request);
    };
  const member = (t: TeamFixture, request: FixtureRequest): TeamRosterMemberOut | undefined =>
    t.roster.find((m) => m.user_id === request.params.user_id);

  return {
    "GET /v1/engagements/{engagement_id}/team": (request) => {
      const t = find(request);
      return t === undefined ? json(NOT_FOUND, 404) : json(t.roster);
    },
    "GET /v1/engagements/{engagement_id}/team/approval": (request) => {
      const t = find(request);
      return t === undefined ? json(NOT_FOUND, 404) : json(t.approval);
    },
    "GET /v1/engagements/{engagement_id}/team/candidates": (request) => {
      const t = find(request);
      if (t === undefined) return json(NOT_FOUND, 404);
      const on = new Set(t.roster.map((m) => m.user_id));
      return json(t.candidates.filter((c) => !on.has(c.user_id)));
    },
    "GET /v1/engagements/{engagement_id}/eqr/candidates": (request) => {
      const t = find(request);
      return t === undefined ? json(NOT_FOUND, 404) : json(t.eqr);
    },
    "POST /v1/engagements/{engagement_id}/team": write("engagement.member_add", (t, request) => {
      const body = request.body as TeamMemberIn;
      if (t.roster.some((m) => m.user_id === body.user_id)) {
        return json({ detail: "member_exists" }, 409);
      }
      const who = t.candidates.find((c) => c.user_id === body.user_id);
      if (who === undefined) return json(NOT_FOUND, 404);
      const added: TeamRosterMemberOut = {
        user_id: who.user_id,
        display_name: who.display_name,
        role: body.role,
        budget_hours: body.budget_hours == null ? null : String(body.budget_hours),
        shown_on_portal: false,
        proposed_at: now,
        independence: "requested",
      };
      t.roster.push(added);
      if (t.approval.approved_at != null) {
        t.approval = {
          ...t.approval,
          changed: true,
          added_since: [...(t.approval.added_since ?? []), who.user_id],
        };
      }
      t.record.record = {
        ...t.record.record,
        tab_counts: { ...t.record.record.tab_counts, team: t.roster.length },
      };
      return json(t.roster, 201);
    }),
    "PUT /v1/engagements/{engagement_id}/team/{user_id}": write(
      "engagement.member_add",
      (t, request) => {
        const m = member(t, request);
        if (m === undefined) return json(NOT_FOUND, 404);
        const body = request.body as TeamRoleIn;
        Object.assign(m, {
          ...(body.role == null ? {} : { role: body.role }),
          ...(body.budget_hours == null ? {} : { budget_hours: String(body.budget_hours) }),
        });
        return json(t.roster);
      },
    ),
    "DELETE /v1/engagements/{engagement_id}/team/{user_id}": write(
      "engagement.member_remove",
      (t, request) => {
        const m = member(t, request);
        if (m === undefined) return json(NOT_FOUND, 404);
        t.roster = t.roster.filter((x) => x !== m);
        return json(t.roster);
      },
    ),
    "PUT /v1/engagements/{engagement_id}/team/{user_id}/portal-visibility": write(
      "engagement.update",
      (t, request) => {
        const m = member(t, request);
        if (m === undefined) return json(NOT_FOUND, 404);
        if (m.independence !== "confirmed") return json({ detail: "gate_unmet" }, 409);
        m.shown_on_portal = (request.body as PortalVisibilityIn).shown_on_portal;
        const out: PortalVisibilityOut = {
          user_id: m.user_id,
          shown_on_portal: m.shown_on_portal,
        };
        return json(out);
      },
    ),
    "POST /v1/engagements/{engagement_id}/independence/reminders": write(
      "independence.remind",
      (t, request) => {
        const ids = (request.body as RemindersIn).user_ids;
        const pending = new Set(
          t.roster.filter((m) => m.independence !== "confirmed").map((m) => m.user_id),
        );
        if (ids.length === 0 || ids.some((id) => !pending.has(id))) {
          return json({ detail: "not_requested" }, 422);
        }
        options.seen?.reminders.push(...ids);
        const out: RemindersOut = { reminded_user_ids: ids };
        return json(out);
      },
    ),
    "POST /v1/engagements/{engagement_id}/eqr": write("eqr.assign", (t, request) => {
      const { user_id } = request.body as EqrIn;
      if (t.roster.some((m) => m.user_id === user_id && !isEqr(m))) {
        return json({ detail: "eqr_on_team" }, 409);
      }
      const c = t.eqr.find((x) => x.user_id === user_id);
      if (c === undefined) return json(NOT_FOUND, 404);
      if (c.eligibility !== "eligible") {
        return json(
          {
            detail: "eqr_not_eligible",
            facts: { failing: c.checks.filter((k) => k.result === "fail").map((k) => k.code) },
          },
          409,
        );
      }
      const previous = t.roster.find(isEqr);
      t.roster = t.roster.filter((m) => !isEqr(m));
      t.roster.push({
        user_id: c.user_id,
        display_name: c.display_name,
        role: EQR,
        budget_hours: previous?.budget_hours ?? null,
        shown_on_portal: false,
        proposed_at: now,
        independence: "requested",
      });
      t.eqr = t.eqr.map((x) => ({ ...x, current: x.user_id === user_id }));
      const out: AbacusModulesEngagementsAcceptanceContractEqrOut = {
        engagement_id: t.record.record.id,
        user_id,
        eligibility: c.eligibility,
        checks: c.checks,
      };
      return json(out);
    }),
  };
}
