// ENG-03 New engagement wizard, core: one fixture scenario per artboard P-07-T21 builds
// (docs/screens/ENG-03.md), all seen by Hannah Leclerc. a, b, c and f at Tue Sep 8, 2026, 9:40
// AM CT (the draft saved 9:39 AM); d at Mon Aug 24, 2026, 10:05 AM CT, before the Granite Peak
// acceptance decision. The catalogue is the 18 selectable types of the contract (no
// Single audit type, D10), labelled as the handoff draws them:
//
//   a  step 1, Fairhaven Foods 401(k) Plan, EBP audit, continuance approved Aug 28 (G1 met)
//   b  step 2, §103(a)(3)(C) scope
//   c  step 4, Fiona Nash's independence requested and unconfirmed (G2 blocks her only)
//   d  Granite Peak Outdoor Supply, Inc., FS audit, G1 unmet: Next disabled, Start acceptance
//   f  a, read for the Single audit tile's tooltip
//
// e, g and h are P-07-T34's. They live under fixtures/ (dev and test only).

import type {
  AcceptanceStartedOut,
  ClientRecordOut,
  EngagementDraftOut,
  EngagementDraftPatchIn,
  EngagementFromDraftOut,
  EngagementTypeCatalogueOut,
  EngagementTypeEntryOut,
} from "@abacus/api-client";
import {
  type FixtureHandler,
  type Scenario,
  defineScenarios,
  json,
} from "../../app-core/fixture-mode";
import { seedScenario } from "../scenario";
import { getSeed } from "../seed";
import { clientRecords, GRANITE_PEAK } from "../seed/client-records";
import { entityIdOf, slugOfClient } from "../seed/clients";
import { slugOf } from "../seed/people";
import { stableId } from "../seed/prng";

const E0 = seedScenario();
const seed = getSeed();

/** Tue Sep 8, 2026, 9:40 AM CT (a, b, c, f). */
export const CLOCK_SEP_8 = "2026-09-08T09:40:00-05:00";
/** Mon Aug 24, 2026, 10:05 AM CT (d). */
export const CLOCK_AUG_24 = "2026-08-24T10:05:00-05:00";

const user = (name: string): string => stableId(`user:${slugOf(name)}`);

type Entry = [
  EngagementTypeEntryOut["code"],
  EngagementTypeEntryOut["engagement_type"],
  EngagementTypeEntryOut["family"],
  EngagementTypeEntryOut["work_item_kind"],
  string,
  string,
  ("attest" | null)?,
];

const CATALOGUE: readonly Entry[] = [
  ["form_1040", "tax_compliance", "tax", "tax_return", "Form 1040", "Individual"],
  ["form_1041", "tax_compliance", "tax", "tax_return", "Form 1041", "Trust or estate"],
  ["form_1065", "tax_compliance", "tax", "tax_return", "Form 1065", "Partnership"],
  ["form_1120s", "tax_compliance", "tax", "tax_return", "Form 1120-S", "S corporation"],
  ["form_1120", "tax_compliance", "tax", "tax_return", "Form 1120", "C corporation"],
  ["form_990", "tax_compliance", "tax", "tax_return", "Form 990", "Exempt organization"],
  ["forms_706_709", "tax_compliance", "tax", "tax_return", "Forms 706 / 709", "Estate & gift"],
  [
    "notice_response",
    "notice_response",
    "tax",
    "notice",
    "Notice response",
    "IRS or state notice",
  ],
  ["ebp_audit", "ebp_audit", "audit_assurance", "assurance", "EBP audit", "AU-C 703 · ERISA"],
  ["fs_audit", "fs_audit", "audit_assurance", "assurance", "FS audit", "GAAS nonissuer"],
  ["review", "review", "audit_assurance", "assurance", "Review", "AR-C 90"],
  ["compilation", "compilation", "audit_assurance", "assurance", "Compilation", "AR-C 80"],
  ["preparation", "preparation", "audit_assurance", "assurance", "Preparation", "AR-C 70"],
  [
    "agreed_upon_procedures",
    "agreed_upon_procedures",
    "audit_assurance",
    "assurance",
    "Agreed-upon procedures",
    "AT-C 215",
  ],
  ["soc1", "soc1", "audit_assurance", "assurance", "SOC 1", "AT-C 320", "attest"],
  ["soc2", "soc2", "audit_assurance", "assurance", "SOC 2", "AT-C 205", "attest"],
  [
    "cas_monthly_close",
    "cas_monthly_close",
    "cas_advisory",
    "close",
    "Monthly close",
    "Client accounting services",
  ],
  [
    "advisory",
    "advisory",
    "cas_advisory",
    "advisory_project",
    "Advisory project",
    "Scoped project",
  ],
];

export const TYPES: EngagementTypeCatalogueOut = {
  items: CATALOGUE.map(([code, engagementType, family, kind, label, line, entitlement]) => ({
    code,
    engagement_type: engagementType,
    family,
    work_item_kind: kind,
    label,
    standard_line: line,
    availability: entitlement == null ? "available" : "needs_entitlement",
    entitlement: entitlement ?? null,
    steps: [],
  })),
};

const FAIRHAVEN = "Fairhaven Foods, Inc.";
const FAIRHAVEN_PLAN = "Fairhaven Foods 401(k) Plan";
const fairhavenId = stableId(`client:${slugOfClient(FAIRHAVEN)}`);
const fairhavenPlanId = entityIdOf(slugOfClient(FAIRHAVEN), FAIRHAVEN_PLAN);

const FAIRHAVEN_RECORD: ClientRecordOut = {
  id: fairhavenId,
  name: FAIRHAVEN,
  kind: "plan_sponsor",
  status: "active",
  is_attest_client: true,
  portal_status: "active",
  entities: [{ id: fairhavenPlanId, name: FAIRHAVEN_PLAN, entity_type: "ebp_plan" }],
  tab_counts: { engagements: 1, relationships: 0 },
  version: 1,
};

function draft(id: string, over: Partial<EngagementDraftOut>): EngagementDraftOut {
  return {
    id,
    created_by: user("Hannah Leclerc"),
    client_id: fairhavenId,
    client_entity_id: fairhavenPlanId,
    type_code: "ebp_audit",
    step: "client_type",
    payload: {
      name: "PY2025 EBP Audit",
      standards_code: "GAAS nonissuer · periods ending 12/31/2025 · AU-C 703",
      scope_code: "limited_scope",
      fiscal_period_start: "2025-01-01",
      fiscal_period_end: "2025-12-31",
      team: [
        { user_id: user("Margaret Okonkwo"), role: "engagement_partner" },
        { user_id: user("Laura Kemp"), role: "manager" },
        { user_id: user("Caleb Dunn"), role: "senior" },
        { user_id: user("Fiona Nash"), role: "staff" },
      ],
      eqr_user_id: user("Celia Marsh"),
    },
    gates: [
      {
        gate: "G1",
        met: true,
        met_at: "2026-08-28T15:00:00Z",
        met_by_user_id: user("Margaret Okonkwo"),
      },
      {
        gate: "G2",
        met: false,
        blockers: [
          { type: "user", id: user("Fiona Nash"), reason_code: "independence_requested" },
        ],
      },
      { gate: "G3", met: false },
    ],
    saved_at: "2026-09-08T14:39:00Z",
    version: 3,
    allowed_actions: ["engagement.create"],
    ...over,
  };
}

const FAIRHAVEN_DRAFT = stableId("engagement-draft:fairhaven:py2025");
const GRANITE_DRAFT = stableId("engagement-draft:granite-peak:fy2026");
const granite = clientRecords(seed)[GRANITE_PEAK].record;

function handlers(start: EngagementDraftOut): Record<string, FixtureHandler> {
  let current = structuredClone(start);
  const records: Record<string, ClientRecordOut> = {
    [FAIRHAVEN_RECORD.id]: FAIRHAVEN_RECORD,
    [granite.id]: granite,
  };
  return {
    ...E0.handlers,
    "GET /v1/engagement-types": () => json(TYPES),
    "GET /v1/clients/{client_id}": (r) => {
      const found = records[r.params.client_id ?? ""];
      return found === undefined ? json({ detail: "not found" }, 404) : json(found);
    },
    "POST /v1/engagement-drafts": () => json(current, 201),
    "GET /v1/engagement-drafts/{draft_id}": (r) =>
      r.params.draft_id === current.id ? json(current) : json({ detail: "not found" }, 404),
    "PATCH /v1/engagement-drafts/{draft_id}": (r) => {
      const body = r.body as EngagementDraftPatchIn;
      if (body.seen_version !== current.version) {
        return json({ detail: "stale_version", facts: { draft_id: current.id } }, 409);
      }
      current = {
        ...current,
        ...(body.step == null ? {} : { step: body.step }),
        ...(body.type_code === undefined
          ? {}
          : {
              type_code: (body.type_code ?? null) as (EngagementDraftOut["type_code"] & {}) | null,
            }),
        ...(body.payload == null ? {} : { payload: body.payload }),
        version: current.version + 1,
        saved_at: "2026-09-08T14:40:00Z",
      };
      return json(current);
    },
    "DELETE /v1/engagement-drafts/{draft_id}": () =>
      json({ draft_id: current.id, discarded_at: "2026-09-08T14:40:00Z" }),
    "POST /v1/engagement-drafts/{draft_id}/start-acceptance": () => {
      const out: AcceptanceStartedOut = {
        draft_id: current.id,
        engagement_id: stableId(`engagement:prospect:${current.id}`),
        acceptance_record_id: stableId(`acceptance:${current.id}`),
        engagement_status: "prospect",
      };
      return json(out);
    },
    "POST /v1/engagement-drafts/{draft_id}/create": () => {
      if (current.gates?.find((g) => g.gate === "G1")?.met !== true) {
        return json({ detail: "gate_unmet", facts: { gate: "G1" } }, 409);
      }
      const out: EngagementFromDraftOut = {
        engagement_id: stableId(`engagement:created:${current.id}`),
        engagement_status: "accepted",
        work_item_ids: [stableId(`work-item:created:${current.id}`)],
        independence_requested_user_ids: [user("Fiona Nash")],
      };
      return json(out, 201);
    },
  };
}

function at(state: string, clock: string, d: EngagementDraftOut): Scenario {
  return { state, persona: "hannah-leclerc", clock, handlers: handlers(d) };
}

const BUILD = {
  a: () => at("a", CLOCK_SEP_8, draft(FAIRHAVEN_DRAFT, {})),
  b: () => at("b", CLOCK_SEP_8, draft(FAIRHAVEN_DRAFT, { step: "standards_methodology" })),
  c: () => at("c", CLOCK_SEP_8, draft(FAIRHAVEN_DRAFT, { step: "team_independence" })),
  d: () =>
    at(
      "d",
      CLOCK_AUG_24,
      draft(GRANITE_DRAFT, {
        client_id: granite.id,
        client_entity_id: granite.entities[0]?.id ?? null,
        type_code: "fs_audit",
        payload: { name: "FY2026 Financial Statement Audit" },
        gates: [
          {
            gate: "G1",
            met: false,
            blockers: [{ type: "acceptance", id: granite.id, reason_code: "not_decided" }],
          },
          { gate: "G2", met: false },
          { gate: "G3", met: false },
        ],
        saved_at: "2026-08-24T15:04:00Z",
        allowed_actions: ["engagement.create", "client.intake"],
      }),
    ),
  f: () => at("f", CLOCK_SEP_8, draft(FAIRHAVEN_DRAFT, {})),
} as const;

export const scenarios = defineScenarios({
  a: BUILD.a(),
  b: BUILD.b(),
  c: BUILD.c(),
  d: BUILD.d(),
  f: BUILD.f(),
});

/** A scenario with fresh handler state: its draft as the artboard opens it (tests that write). */
export function freshScenario(state: keyof typeof BUILD): Scenario {
  return BUILD[state]();
}

export type Eng03State = keyof typeof scenarios;

export const OPENS: Readonly<Record<Eng03State, string>> = {
  a: FAIRHAVEN_DRAFT,
  b: FAIRHAVEN_DRAFT,
  c: FAIRHAVEN_DRAFT,
  d: GRANITE_DRAFT,
  f: FAIRHAVEN_DRAFT,
};
