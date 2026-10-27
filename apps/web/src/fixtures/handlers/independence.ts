// The independence routes in fixture mode (P-07-T48; docs/contracts/acceptance-independence.md),
// answering as the live routes do (P-07-T41): the summary with each member's own confirmation,
// the NAS matrix, rotation, one conflict check, and the writes, each the caller's own (a member
// confirms or declines only for themself; only the engagement partner concludes, once every
// precondition holds; reminders by a partner or manager). Typed with the generated client.

import type {
  ConflictCheckOut,
  IndependenceConclusionStatus,
  IndependenceSummaryOut,
  MemberConfirmationOut,
  NasOut,
  RotationOut,
} from "@abacus/api-client";
import { type FixtureHandler, type FixtureRequest, json } from "../../app-core/fixture-mode";
import { DEFAULT_PERSONA } from "../handlers";
import { stableId } from "../seed/prng";

const NOT_FOUND = { detail: "not_found" };

export interface IndependenceFixture {
  engagementId: string;
  members: MemberConfirmationOut[];
  attest: boolean;
  nas: NasOut;
  rotation: RotationOut;
  check: ConflictCheckOut | null;
  /** An open breach (CLI-08 g). */
  breach: boolean;
  conclusion: IndependenceSummaryOut["conclusion"];
  /** ISO time the writes are stamped with. */
  now: string;
}

const LEADS = new Set(["engagement_partner", "manager"]);
const PARTNER = new Set(["engagement_partner"]);

function summaryOf(f: IndependenceFixture, viewer: string): IndependenceSummaryOut {
  const me = f.members.find((m) => m.user_id === viewer);
  const confirmed = f.members.filter((m) => m.confirmation === "confirmed").length;
  const blockers: NonNullable<IndependenceSummaryOut["blockers"]> = [
    ...f.members
      .filter((m) => m.confirmation !== "confirmed")
      .map((m) => ({
        reason_code:
          m.confirmation === "declined"
            ? ("member_declined" as const)
            : ("member_not_confirmed" as const),
        ref_id: m.user_id,
        ref_type: "user",
      })),
    ...(f.breach
      ? [{ reason_code: "breach_open" as const, ref_id: f.engagementId, ref_type: "breach" }]
      : []),
  ];
  const actions = ["independence.read"];
  if (me !== undefined) actions.push("independence.confirm");
  if (me !== undefined && LEADS.has(me.role)) actions.push("independence.remind", "nas.evaluate");
  if (me !== undefined && PARTNER.has(me.role)) actions.push("independence.conclude");
  return {
    engagement_id: f.engagementId,
    attest_client: f.attest,
    confirmed,
    total: f.members.length,
    // A member sees only their own decline note; the engagement partner sees every one.
    members: f.members.map((m) =>
      m.user_id === viewer || (me !== undefined && LEADS.has(me.role))
        ? m
        : { ...m, decline_note: null },
    ),
    blockers,
    conclusion: f.conclusion ?? null,
    ske_designee_contact_id: f.nas.ske_designee_contact_id ?? null,
    allowed_actions: actions,
  };
}

export function independenceHandlers(f: IndependenceFixture): Record<string, FixtureHandler> {
  const viewer = (r: FixtureRequest): string => stableId(`user:${r.persona ?? DEFAULT_PERSONA}`);
  const mine = (r: FixtureRequest): boolean => r.params.engagement_id === f.engagementId;
  const self = (r: FixtureRequest): MemberConfirmationOut | undefined =>
    f.members.find((m) => m.user_id === viewer(r));
  return {
    "GET /v1/engagements/{engagement_id}/independence": (r) =>
      mine(r) ? json(summaryOf(f, viewer(r))) : json(NOT_FOUND, 404),
    "GET /v1/engagements/{engagement_id}/independence/nas": (r) =>
      mine(r) ? json(f.nas) : json(NOT_FOUND, 404),
    "GET /v1/engagements/{engagement_id}/independence/rotation": (r) =>
      mine(r) ? json(f.rotation) : json(NOT_FOUND, 404),
    "GET /v1/conflict-checks/{check_id}": (r) =>
      f.check !== null && r.params.check_id === f.check.id ? json(f.check) : json(NOT_FOUND, 404),
    "POST /v1/engagements/{engagement_id}/independence/confirm": (r) => {
      if (!mine(r)) return json(NOT_FOUND, 404);
      const me = self(r);
      if (me === undefined) return json({ detail: "forbidden" }, 403);
      const body = r.body as { statement_codes?: unknown[]; statement_version?: string } | null;
      if ((body?.statement_codes ?? []).length !== 3) {
        return json({ detail: "invalid", facts: { field: "statement_codes" } }, 422);
      }
      Object.assign(me, {
        confirmation: "confirmed",
        answered_at: f.now,
        statement_version: body?.statement_version ?? null,
        decline_note: null,
      });
      return json({
        engagement_id: f.engagementId,
        user_id: me.user_id,
        confirmation: "confirmed",
        answered_at: f.now,
      });
    },
    "POST /v1/engagements/{engagement_id}/independence/decline": (r) => {
      if (!mine(r)) return json(NOT_FOUND, 404);
      const me = self(r);
      if (me === undefined) return json({ detail: "forbidden" }, 403);
      const note = (r.body as { note?: string } | null)?.note ?? "";
      Object.assign(me, { confirmation: "declined", answered_at: f.now, decline_note: note });
      return json({
        engagement_id: f.engagementId,
        user_id: me.user_id,
        confirmation: "declined",
        answered_at: f.now,
      });
    },
    "POST /v1/engagements/{engagement_id}/independence/reminders": (r) => {
      if (!mine(r)) return json(NOT_FOUND, 404);
      const me = self(r);
      if (me === undefined || !LEADS.has(me.role)) return json({ detail: "forbidden" }, 403);
      const ids = (r.body as { user_ids?: string[] } | null)?.user_ids ?? [];
      for (const id of ids) {
        const m = f.members.find((x) => x.user_id === id);
        if (m === undefined || m.confirmation === "confirmed") {
          return json({ detail: "invalid", facts: { user_id: id } }, 422);
        }
        m.reminder_count = (m.reminder_count ?? 0) + 1;
      }
      return json({ reminded_user_ids: ids });
    },
    "POST /v1/engagements/{engagement_id}/independence/conclude": (r) => {
      if (!mine(r)) return json(NOT_FOUND, 404);
      const me = self(r);
      if (me === undefined || !PARTNER.has(me.role)) return json({ detail: "forbidden" }, 403);
      if (summaryOf(f, me.user_id).blockers?.length !== 0) {
        return json({ detail: "independence_preconditions_unmet" }, 409);
      }
      const option = (r.body as { option?: IndependenceConclusionStatus } | null)?.option;
      f.conclusion = {
        id: `${f.engagementId}-conclusion`,
        option: option ?? "independent",
        concluded_by: me.user_id,
        concluded_at: f.now,
      };
      return json(f.conclusion);
    },
  };
}
