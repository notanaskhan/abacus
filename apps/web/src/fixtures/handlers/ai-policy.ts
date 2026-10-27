// Fixture handlers for the AI-policy contract v1 (G-02-T15; docs/contracts/ai-policy.md): ADM-04
// as the live routes will answer it (G-02-T24). Margaret Okonkwo (the QM owner) drafts and
// requests publication; Daniel Reyes (partner) approves; anyone else reads. A draft that loosens
// a locked cell answers 422 `policy_loosening_refused` with the cell's path; the requester
// approving her own version 409 `approver_must_differ`. Fixture requests carry no headers, so
// If-Match (409 `stale_version`) is the live route's alone.
import type { AiPolicySections, AiPolicyVersionOut } from "@abacus/api-client";
import { type FixtureHandler, type FixtureRequest, json } from "../../app-core/fixture-mode";
import {
  ACTIONS_DANIEL,
  ACTIONS_GRACE,
  ACTIONS_MARGARET,
  ACTIONS_READ,
  type AiPolicyView,
  SECTIONS_V3,
  SECTIONS_V4,
  V4_AWAITING,
  V4_PUBLISHED,
  VERSIONS,
  draftOf,
  policyOf,
  versionDetail,
} from "../seed/ai-policy";
import { DANIEL, MARGARET } from "../seed/governance";

const FORBIDDEN = { detail: "forbidden" };
const NOT_FOUND = { detail: "not found" };
const QM_OWNER = "margaret-okonkwo";
const APPROVER = "daniel-reyes";

const personaOf = (request: FixtureRequest): string => request.persona ?? QM_OWNER;

function actionsOf(persona: string): string[] {
  if (persona === QM_OWNER) return ACTIONS_MARGARET;
  if (persona === APPROVER) return ACTIONS_DANIEL;
  if (persona === "grace-holloway") return ACTIONS_GRACE;
  return ACTIONS_READ;
}

/** The stricter-only validator's fixture half (AC-38): the locked cells and the floors. */
function loosened(sections: AiPolicySections): string | null {
  if (sections.policy_principal.on) return "policy_principal.on";
  const accepted = sections.gates.find((g) => g.policy_acceptance_on === true);
  if (accepted !== undefined) return `gates.${accepted.action_key}.policy_acceptance_on`;
  if (sections.client_data.require_7216_consent === false) {
    return "client_data.require_7216_consent";
  }
  if (sections.client_data.client_drafts_enabled === true) {
    return "client_data.client_drafts_enabled";
  }
  if ((sections.governance.trace_retention_years ?? 7) < 7) {
    return "governance.trace_retention_years";
  }
  if (sections.autonomy.level > 1) return "autonomy.level";
  return null;
}

export interface AiPolicyOptions {
  view?: AiPolicyView;
}

export function aiPolicyHandlers(options: AiPolicyOptions = {}): Record<string, FixtureHandler> {
  let view: AiPolicyView = options.view ?? "a";
  let draft = draftOf(view === "b" ? SECTIONS_V4 : SECTIONS_V3);
  let pending: AiPolicyVersionOut | null = view === "awaiting" ? V4_AWAITING : null;

  return {
    "GET /v1/firm/ai-policy": (request) => {
      const policy = policyOf(view, actionsOf(personaOf(request)));
      return json({ ...policy, pending, draft });
    },
    "GET /v1/firm/ai-policy/versions": () => {
      const items = [...(view === "g" ? [V4_PUBLISHED] : []), ...VERSIONS]
        .map((v) => (view === "g" && v.version_no === 3 ? { ...v, superseded: true } : v))
        .sort((a, b) => b.version_no - a.version_no);
      return json({
        items,
        next_cursor: null,
        total: items.length,
        total_capped: false,
        counts: {},
        facets: {},
      });
    },
    "GET /v1/firm/ai-policy/versions/{version_no}": ({ params }) => {
      const detail = versionDetail(Number(params.version_no));
      return detail === null ? json(NOT_FOUND, 404) : json(detail);
    },
    "GET /v1/firm/ai-policy/effective": ({ query }) => {
      const type = (query.get("engagement_type") ??
        "fs_audit") as keyof AiPolicySections["auto_mode_defaults"];
      const policy = policyOf(view, []);
      const stored = policy.sections.auto_mode_defaults[type] ?? false;
      return json({
        version_no: policy.effective.version_no,
        effective_from: policy.effective.effective_from,
        engagement_type: type,
        at: query.get("at") ?? "2026-09-14T14:24:00Z",
        autonomy_level: policy.sections.autonomy.level,
        auto_mode: stored,
        auto_mode_effective: stored && !policy.real_firm,
        auto_mode_lock: policy.real_firm ? "real_firm_season_1" : null,
        policy_principal_on: false,
        client_data: policy.sections.client_data,
        firm_paused: false,
      });
    },
    "GET /v1/firm/ai-policy/draft": (request) =>
      personaOf(request) === QM_OWNER ? json(draft) : json(FORBIDDEN, 403),
    "PUT /v1/firm/ai-policy/draft": (request) => {
      if (personaOf(request) !== QM_OWNER) return json(FORBIDDEN, 403);
      const body = request.body as { sections?: AiPolicySections } | undefined;
      const sections = body?.sections ?? draft.sections;
      const field = loosened(sections);
      if (field !== null) {
        return json({ detail: "policy_loosening_refused", facts: { field } }, 422);
      }
      const changed =
        sections.governance.override_tolerance_pct !==
        SECTIONS_V3.governance.override_tolerance_pct;
      draft = {
        ...draftOf(changed ? SECTIONS_V4 : SECTIONS_V3),
        version: draft.version + 1,
      };
      return json(draft);
    },
    "DELETE /v1/firm/ai-policy/draft": (request) => {
      if (personaOf(request) !== QM_OWNER) return json(FORBIDDEN, 403);
      draft = draftOf(SECTIONS_V3);
      return json(draft);
    },
    "POST /v1/firm/ai-policy/versions": (request) => {
      if (personaOf(request) !== QM_OWNER) return json(FORBIDDEN, 403);
      const body = request.body as { approver_user_id?: string } | undefined;
      if (body?.approver_user_id === MARGARET.user_id) {
        return json({ detail: "approver_must_differ" }, 409);
      }
      pending = { ...V4_AWAITING, approver: DANIEL };
      view = "awaiting";
      return json(pending, 201);
    },
    "POST /v1/firm/ai-policy/versions/{version_no}/approve": (request) => {
      const persona = personaOf(request);
      if (persona === QM_OWNER) return json({ detail: "approver_must_differ" }, 409);
      if (persona !== APPROVER) return json(FORBIDDEN, 403);
      if (pending === null) return json(NOT_FOUND, 404);
      pending = null;
      view = "g";
      return json(V4_PUBLISHED);
    },
    "POST /v1/firm/ai-policy/versions/{version_no}/decline": (request) => {
      if (personaOf(request) !== APPROVER) return json(FORBIDDEN, 403);
      if (pending === null) return json(NOT_FOUND, 404);
      const declined: AiPolicyVersionOut = {
        ...pending,
        state: "declined",
        decided_by: DANIEL,
        decided_at: "2026-09-14T14:31:00Z",
      };
      pending = null;
      return json(declined);
    },
    "POST /v1/firm/ai-policy/versions/{version_no}/withdraw": (request) => {
      if (personaOf(request) !== QM_OWNER) return json(FORBIDDEN, 403);
      if (pending === null) return json(NOT_FOUND, 404);
      const withdrawn: AiPolicyVersionOut = { ...pending, state: "withdrawn" };
      pending = null;
      return json(withdrawn);
    },
  };
}
