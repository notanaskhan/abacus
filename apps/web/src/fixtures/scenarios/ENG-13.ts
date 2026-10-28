// ENG-13 Roll forward: one fixture scenario per artboard P-07-T60 builds (docs/screens/ENG-13.md),
// over the roll-forward v2 routes (P-07-T55; docs/contracts/engagements-v2.md §8a):
//
//   a  Laura Kemp, Mon Nov 16, 2026, 10:15 AM CT: Tessellate SOC 2 Type 2 (delivered) into
//      Oct 1, 2026 – Sep 30, 2027, step 2 What to carry (the SOC 2 carry rows fixture-only, X-01)
//   b  the same, step 3 Template version: "BH SOC 2 · TSC 2017 (rev. 2022)" v1, Current
//   c  Hannah Leclerc, 11:00 AM: Granite Peak FY2026 → FY2027, step 3 with the FS v5 → FS v6
//      conflicts (fixture-only until K-03)
//   d  Hannah Leclerc, Mon Jan 11, 2027, 9:30 AM CT: Northwind PY2025 EBP Audit (archived) into
//      PY2026, step 2: the v1 rows live, 24 requests as Draft
//   e  Laura Kemp, Nov 16, 10:15 AM: Tessellate, step 5 Review and Create
//
// The v1 categories (team, template, request list, prior-year notes) are the API's; the attest and
// structure rows, the bridge-letter toggle, learned context and the conflicts are the handoff's
// preview, passed to the screen only in fixture builds (`PREVIEWS`), never served. They live
// under fixtures/ (dev and test only).

import type {
  EngagementStatus,
  RollForwardCreatedOut,
  RollForwardDraftDiscardedOut,
  RollForwardDraftOut,
  RollForwardDraftPatchIn,
  RollForwardTeamMemberOut,
} from "@abacus/api-client";
import { type Scenario, defineScenarios, json } from "../../app-core/fixture-mode";
import { seedScenario } from "../scenario";
import { getSeed } from "../seed";
import { slugOf } from "../seed/people";
import { stableId } from "../seed/prng";

const E0 = seedScenario();
const seed = getSeed();

/** Mon Nov 16, 2026, 10:15 AM CT (a, b, e). */
export const CLOCK_NOV_16 = "2026-11-16T10:15:00-06:00";
/** Mon Nov 16, 2026, 11:00 AM CT (c). */
export const CLOCK_NOV_16_11 = "2026-11-16T11:00:00-06:00";
/** Mon Jan 11, 2027, 9:30 AM CT (d). */
export const CLOCK_JAN_11 = "2027-01-11T09:30:00-06:00";

export type Eng13State = "a" | "b" | "c" | "d" | "e";
export type Eng13Step = "source" | "carry" | "template" | "team" | "review";

/** A carry row only the handoff draws (fixture builds): Carry · Skip, a toggle, or a line. */
export interface PreviewRow {
  label: string;
  detail: string;
  control: "carry" | "toggle" | "info" | "muted";
  pill?: string;
}
export interface PreviewCard {
  title: string;
  tag?: string;
  rows: readonly PreviewRow[];
}
export interface PreviewConflict {
  label: string;
  options: readonly [string, string];
}
/** What a fixture-only artboard adds (DEC-805: never served by the v1 API). */
export interface CarryPreview {
  cards: readonly PreviewCard[];
  /** The summary card's extra lines ("38 criteria · 74 controls", "2 triggers", …). */
  carrying: readonly string[];
  /** Requests the preview adds to the list (a's bridge-letter request: 212 + 1 = 213). */
  extraRequests?: number;
  /** c: the template changed, its change list and the two choices Next waits for. */
  conflicts?: {
    banner: string;
    changes: readonly string[];
    rows: readonly PreviewConflict[];
  };
}

const person = (name: string): string => stableId(`user:${slugOf(name)}`);

interface Source {
  key: string;
  engagementId: string;
  name: string;
  status: EngagementStatus;
  start: string;
  end: string;
  targetName: string;
  targetStart: string;
  targetEnd: string;
  team: readonly (readonly [string, string])[];
  template: RollForwardDraftOut["catalogue"]["template"];
  requests: number;
}

const NORTHWIND_ENGAGEMENT = seed.engagementIds.A1 ?? stableId("engagement:northwind:py2025");
const GRANITE_ENGAGEMENT = seed.engagementIds.A2 ?? stableId("engagement:granite-peak:fy2026");
const engagement = (id: string) => seed.engagements.find((e) => e.id === id);
/** The same day a year on, as the server's `next_year` (ISO dates). */
const nextYear = (day: string): string => `${String(Number(day.slice(0, 4)) + 1)}${day.slice(4)}`;
const granite = engagement(GRANITE_ENGAGEMENT);
const northwind = engagement(NORTHWIND_ENGAGEMENT);

const TESSELLATE: Source = {
  key: "tessellate",
  engagementId: stableId("engagement:tessellate:soc2:fy2026"),
  name: "SOC 2 Type 2",
  status: "delivered",
  start: "2025-10-01",
  end: "2026-09-30",
  targetName: "SOC 2 Type 2",
  targetStart: "2026-10-01",
  targetEnd: "2027-09-30",
  team: [
    ["Celia Marsh", "engagement_partner"],
    ["Laura Kemp", "manager"],
    ["Jasper Bell", "senior"],
    ["Kira Ross", "staff"],
  ],
  template: {
    template_id: stableId("methodology-template:bh-soc2"),
    template_name: "BH SOC 2 · TSC 2017 (rev. 2022)",
    source_version: 1,
    current_version_id: stableId("methodology-version:bh-soc2:v1"),
    current_version: 1,
    current: true,
  },
  requests: 212,
};

const GRANITE: Source = {
  key: "granite-peak",
  engagementId: GRANITE_ENGAGEMENT,
  name: granite?.name ?? "",
  status: "delivered",
  start: granite?.fiscal_period_start ?? "",
  end: granite?.fiscal_period_end ?? "",
  targetName: (granite?.name ?? "").replace("FY2026", "FY2027"),
  targetStart: nextYear(granite?.fiscal_period_start ?? "0000-01-01"),
  targetEnd: nextYear(granite?.fiscal_period_end ?? "0000-12-31"),
  team: [
    ["Margaret Okonkwo", "engagement_partner"],
    ["Hannah Leclerc", "manager"],
    ["Marcus Delaney", "senior"],
    ["Ana Cruz", "staff"],
  ],
  template: {
    template_id: stableId("methodology-template:bh-audit-fs"),
    template_name: "BH Audit Methodology · FS",
    source_version: 5,
    current_version_id: stableId("methodology-version:bh-audit-fs:v6"),
    current_version: 6,
    current: false,
  },
  requests: (seed.requestItems[GRANITE_ENGAGEMENT] ?? []).length,
};

const NORTHWIND: Source = {
  key: "northwind",
  engagementId: NORTHWIND_ENGAGEMENT,
  name: northwind?.name ?? "",
  status: "archived",
  start: northwind?.fiscal_period_start ?? "",
  end: northwind?.fiscal_period_end ?? "",
  targetName: (northwind?.name ?? "").replace("PY2025", "PY2026"),
  targetStart: nextYear(northwind?.fiscal_period_start ?? "0000-01-01"),
  targetEnd: nextYear(northwind?.fiscal_period_end ?? "0000-12-31"),
  team: [
    ["Margaret Okonkwo", "engagement_partner"],
    ["Hannah Leclerc", "manager"],
    ["Marcus Delaney", "senior"],
    ["Ana Cruz", "staff"],
  ],
  template: {
    template_id: stableId("methodology-template:bh-audit-ebp"),
    template_name: "BH Audit Methodology · EBP",
    source_version: 3,
    current_version_id: stableId("methodology-version:bh-audit-ebp:v3"),
    current_version: 3,
    current: true,
  },
  requests: (seed.requestItems[NORTHWIND_ENGAGEMENT] ?? []).length,
};

const SOURCES: Record<Eng13State, Source> = {
  a: TESSELLATE,
  b: TESSELLATE,
  c: GRANITE,
  d: NORTHWIND,
  e: TESSELLATE,
};

/** The step each artboard opens on. */
export const STEP_OF: Record<Eng13State, Eng13Step> = {
  a: "carry",
  b: "template",
  c: "template",
  d: "carry",
  e: "review",
};

const SAVED_AT: Record<Eng13State, string> = {
  a: "2026-11-16T10:14:00-06:00",
  b: "2026-11-16T10:14:00-06:00",
  c: "2026-11-16T10:59:00-06:00",
  d: "2027-01-11T09:29:00-06:00",
  e: "2026-11-16T10:14:00-06:00",
};

export const OPENS: Record<Eng13State, { source: string; draft: string }> = {
  a: { source: TESSELLATE.engagementId, draft: stableId("roll-forward-draft:tessellate") },
  b: { source: TESSELLATE.engagementId, draft: stableId("roll-forward-draft:tessellate") },
  c: { source: GRANITE.engagementId, draft: stableId("roll-forward-draft:granite-peak") },
  d: { source: NORTHWIND.engagementId, draft: stableId("roll-forward-draft:northwind") },
  e: { source: TESSELLATE.engagementId, draft: stableId("roll-forward-draft:tessellate") },
};

function teamOf(source: Source): RollForwardTeamMemberOut[] {
  return source.team.map(([name, role]) => ({
    user_id: person(name),
    display_name: name,
    role,
    available: true,
  }));
}

export function draftOf(state: Eng13State): RollForwardDraftOut {
  const source = SOURCES[state];
  const team = teamOf(source);
  return {
    id: OPENS[state].draft,
    source: {
      engagement_id: source.engagementId,
      name: source.name,
      status: source.status,
      fiscal_period_start: source.start,
      fiscal_period_end: source.end,
    },
    target_period_start: source.targetStart,
    target_period_end: source.targetEnd,
    name: source.targetName,
    selections: { team: true, template: true, request_list: true, prior_year_notes: true },
    team: team.map((m) => ({ user_id: m.user_id, role: m.role })),
    template_decision: "current",
    version: 3,
    saved_at: SAVED_AT[state],
    created_engagement_id: null,
    catalogue: {
      team,
      template: source.template,
      request_count: source.requests,
      evidence_copied: 0,
    },
    allowed_actions: ["roll_forward.create"],
  };
}

/** The handoff's fixture-only rows per artboard (never served; DEC-805). */
const SOC2_CARDS: readonly PreviewCard[] = [
  {
    title: "Scope and controls",
    rows: [
      {
        label: "Scope and criteria",
        detail:
          "Security · Availability · Confidentiality · 38 criteria (CC1.1–CC9.2 33 · A1.1–A1.3 3 · C1.1–C1.2 2)",
        control: "carry",
      },
      {
        label: "Controls",
        detail:
          "74 controls TES-01 … TES-74 · 58 key · descriptions, owners and test procedures; results and sign-offs start empty",
        control: "carry",
      },
      {
        label: "Framework mappings",
        detail: "ISO/IEC 27001:2022 Annex A · 61 of 74 controls map to 52 of 93",
        control: "carry",
      },
      {
        label: "Subservice organization",
        detail: "Northpeak Cloud · hosting · carve-out · 5 CSOCs",
        control: "carry",
      },
      { label: "Complementary user entity controls", detail: "6 CUECs", control: "carry" },
      {
        label: "Prior-year exceptions",
        detail:
          "E-1 CC6.2 · E-2 CC8.1 · E-3 A1.2 → planning notes on TES-38, TES-52 and TES-67, not results",
        control: "carry",
      },
      {
        label: "Account mappings · Prior-year balances",
        detail: "Not used by SOC engagements",
        control: "muted",
      },
    ],
  },
  {
    title: "Requests and automation",
    rows: [
      {
        label: "Bridge-letter request",
        detail:
          "Add 'Northpeak Cloud SOC 2 report and bridge letter for any gap to Sep 30, 2027' to the request list as Draft",
        control: "toggle",
      },
      {
        label: "Triggers",
        detail:
          "2 · Request evidence uploaded → Evidence screening → All request sheets · Request status changes to Received → Control tester → Control testing",
        control: "carry",
      },
      {
        label: "Sheets and saved views",
        detail: "Control matrix, test sheets and their saved views; rows start unsigned",
        control: "carry",
      },
      {
        label: "GRC connection",
        detail:
          "Drata stays connected on the client (Marisol Vega, Sep 2). Request sync re-maps after Create.",
        control: "info",
      },
    ],
  },
  {
    title: "Learned context · 3",
    tag: "Client · Tessellate",
    rows: [
      {
        label:
          "BambooHR termination dates are effective dates; measure access removal from the effective date.",
        detail: "From E-1 testing (TES-38) · approved by Laura Kemp",
        control: "carry",
        pill: "Approved",
      },
      {
        label:
          "Emergency changes in Jira carry the EMERG label; approval is due within one business day of deployment.",
        detail: "From E-2 (TES-52) · approved by Laura Kemp",
        control: "carry",
        pill: "Approved",
      },
      {
        label:
          "Backup restoration tests are on the on-call calendar from September 2026; request the calendar export with each test.",
        detail: "From the E-3 management response · approved by Laura Kemp",
        control: "carry",
        pill: "Approved",
      },
    ],
  },
];

const SOC2: CarryPreview = {
  cards: SOC2_CARDS,
  carrying: ["38 criteria · 74 controls", "2 triggers", "3 learned-context items"],
  extraRequests: 1,
};

const NORTHWIND_PREVIEW: CarryPreview = {
  cards: [
    {
      title: "Structure and balances",
      rows: [
        {
          label: "Structure",
          detail:
            "26 workpapers (Planning 6 · Fieldwork 3 · Testing 7 · Completion 6 · Reporting 4), unsigned",
          control: "carry",
        },
        {
          label: "Account mappings",
          detail: "Fund list: 5 KRS funds · Harborline Stable Value Fund · BrokerWindow",
          control: "carry",
        },
        {
          label: "Prior-year balances",
          detail: "Net assets available for benefits, 12/31/2025 16,861,000 → beginning balance",
          control: "carry",
        },
        { label: "Triggers", detail: "2", control: "carry" },
      ],
    },
  ],
  carrying: ["26 workpapers", "2 triggers"],
};

const GRANITE_PREVIEW: CarryPreview = {
  cards: [],
  carrying: [],
  conflicts: {
    banner: "Template changed since FY2026: BH Audit Methodology · FS v5 (held Oct 1) → FS v6",
    changes: [
      'Added 3 (BH-FS-700, BH-FS-710, BH-FS-720 — hidden by scoping rule "Group audit = No")',
      "Changed 5",
      "Removed 0",
    ],
    rows: [
      {
        label: "Saved view 'Threshold + random' on BH-FS-430 follows FS v5 sample guidance",
        options: ["Keep", "Use v6"],
      },
      {
        label:
          "Trigger 'Request evidence uploaded → Unrecorded liabilities tester → BH-FS-430': the tester now follows skill BH-SK-430 v2",
        options: ["Keep", "Update"],
      },
    ],
  },
};

/** The fixture-only preview each artboard draws (gallery and tests; the route passes none). */
export const PREVIEWS: Record<Eng13State, CarryPreview> = {
  a: SOC2,
  b: SOC2,
  c: GRANITE_PREVIEW,
  d: NORTHWIND_PREVIEW,
  e: SOC2,
};

function created(state: Eng13State): RollForwardCreatedOut {
  const source = SOURCES[state];
  return {
    engagement_id: stableId(`engagement:${source.key}:rolled-forward`),
    engagement_status: "prospect",
    prior_engagement_id: source.engagementId,
    acceptance_record_id: stableId(`acceptance-record:${source.key}:continuance`),
    requests_created: source.requests,
    independence_requested_user_ids: teamOf(source).map((m) => m.user_id),
    methodology_version_id: source.template?.current_version_id ?? null,
  };
}

const DRAFTS = "/v1/engagements/{engagement_id}/roll-forward/drafts";

/** A fresh scenario for `state`: its own draft store, so a test's saves never leak. */
export function freshScenario(state: Eng13State): Scenario {
  let draft = draftOf(state);
  const viewer: Record<Eng13State, string> = {
    a: "laura-kemp",
    b: "laura-kemp",
    c: "hannah-leclerc",
    d: "hannah-leclerc",
    e: "laura-kemp",
  };
  const clock: Record<Eng13State, string> = {
    a: CLOCK_NOV_16,
    b: CLOCK_NOV_16,
    c: CLOCK_NOV_16_11,
    d: CLOCK_JAN_11,
    e: CLOCK_NOV_16,
  };
  const ours = (params: Record<string, string>): boolean =>
    params.engagement_id === draft.source.engagement_id && params.draft_id === draft.id;
  return {
    ...E0,
    state,
    persona: viewer[state],
    clock: clock[state],
    handlers: {
      ...E0.handlers,
      // The route starts a draft when the URL names none (P-07-T62): the scenario's own.
      [`POST ${DRAFTS}`]: ({ params }) =>
        params.engagement_id === draft.source.engagement_id
          ? json(draft, 201)
          : json({ detail: "not_found" }, 404),
      [`GET ${DRAFTS}/{draft_id}`]: ({ params }) =>
        ours(params) ? json(draft) : json({ detail: "not_found" }, 404),
      [`PATCH ${DRAFTS}/{draft_id}`]: ({ params, body }) => {
        if (!ours(params)) return json({ detail: "not_found" }, 404);
        const change = body as RollForwardDraftPatchIn;
        if (change.seen_version !== draft.version) {
          return json({ detail: "stale_version", facts: { version: draft.version } }, 409);
        }
        const picks = Object.fromEntries(
          Object.entries(change.selections ?? {}).filter(([, v]) => v !== null),
        ) as Partial<RollForwardDraftOut["selections"]>;
        const byId = new Map(draft.catalogue.team.map((m) => [m.user_id, m]));
        draft = {
          ...draft,
          ...(change.name == null ? {} : { name: change.name }),
          ...(change.template_decision == null
            ? {}
            : { template_decision: change.template_decision }),
          selections: { ...draft.selections, ...picks },
          ...(change.team_user_ids == null
            ? {}
            : {
                team: change.team_user_ids.flatMap((id) => {
                  const m = byId.get(id);
                  return m === undefined ? [] : [{ user_id: id, role: m.role }];
                }),
              }),
          version: draft.version + 1,
        };
        return json(draft);
      },
      [`DELETE ${DRAFTS}/{draft_id}`]: ({ params }) =>
        ours(params)
          ? json({
              draft_id: draft.id,
              discarded_at: SAVED_AT[state],
            } satisfies RollForwardDraftDiscardedOut)
          : json({ detail: "not_found" }, 404),
      [`POST ${DRAFTS}/{draft_id}/create`]: ({ params }) => {
        if (!ours(params)) return json({ detail: "not_found" }, 404);
        const out = created(state);
        draft = { ...draft, created_engagement_id: out.engagement_id };
        return json(out, 201);
      },
    },
  };
}

export const scenarios = defineScenarios({
  a: freshScenario("a"),
  b: freshScenario("b"),
  c: freshScenario("c"),
  d: freshScenario("d"),
  e: freshScenario("e"),
});
