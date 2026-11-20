// T-08-T15 (TASK-8841): ENG-07's TY2025 roll-forward manifest in fixture mode, as
// `GET /v1/seasons/{tax_year}/manifests/{id}` and `GET /v1/season-cohorts/{id}/rows` answer them.
// Every figure is the handoff's (spec ACCEPTANCE): 65+30+42+19+38+20 = 214 engagements,
// 68+30+45+19+42+20 = 224 returns, 74+33+48+21+45+20 = 241 binders; created 126 = 65 + 30 + 31.
// eng07.foot.test.ts re-adds them (ADR-050); the screen computes nothing.
import type {
  SeasonAskOut,
  SeasonCohortOut,
  SeasonManifestOut,
  SeasonManifestRowOut,
  SeasonPersonOut,
} from "@abacus/api-client";
import { stableId } from "./prng";

export type Eng07Variant = "draft" | "approved" | "executing" | "agentsOff";

const HASH = "0".repeat(64);
const person = (key: string, initials: string, name: string): SeasonPersonOut => ({
  user_id: stableId(`user:${key}`),
  initials,
  name,
});
export const PEOPLE = {
  na: person("nina-alvarez", "NA", "Nina Alvarez"),
  im: person("isaac-moreau", "IM", "Isaac Moreau"),
  si: person("samuel-ito", "SI", "Samuel Ito"),
  tr: person("tomas-reyes", "TR", "Tomás Reyes"),
  ko: person("kevin-osei", "KO", "Kevin Osei"),
  ds: person("dana-schultz", "DS", "Dana Schultz"),
  rv: person("remy-vidal", "RV", "Remy Vidal"),
  ql: person("quinn-lee", "QL", "Quinn Lee"),
  np: person("nadia-park", "NP", "Nadia Park"),
  dr: person("daniel-reyes", "DR", "Daniel Reyes"),
  gh: person("grace-holloway", "GH", "Grace Holloway"),
};
export const MANIFEST_ID = stableId("season-manifest:ty2025");
const OFFICE = (k: string): string => stableId(`office:${k}`);
export const COHORT_ID = (n: number): string => stableId(`season-cohort:ty2025:${String(n)}`);

type C = readonly [
  n: number,
  office: string,
  segment: SeasonCohortOut["segment"],
  e: number,
  r: number,
  b: number,
  approver: SeasonPersonOut,
];
const COHORTS: readonly C[] = [
  [1, "Chicago", "individuals_trusts", 65, 68, 74, PEOPLE.na],
  [2, "Chicago", "entities_exempt", 30, 30, 33, PEOPLE.na],
  [3, "Denver", "individuals_trusts", 42, 45, 48, PEOPLE.im],
  [4, "Denver", "entities_exempt", 19, 19, 21, PEOPLE.im],
  [5, "New York", "individuals_trusts", 38, 42, 45, PEOPLE.si],
  [6, "New York", "entities_exempt", 20, 20, 20, PEOPLE.tr],
];

function cohort(
  [n, office, segment, e, r, b, approver]: C,
  variant: Eng07Variant,
): SeasonCohortOut {
  const done = n <= 2;
  const c5Approved = n === 5 && variant === "approved";
  const display: SeasonCohortOut["display"] = done
    ? "executed"
    : n === 3
      ? "executing"
      : n === 4
        ? "queued"
        : c5Approved
          ? "queued"
          : n === 5
            ? "review_required"
            : "draft";
  return {
    cohort_id: COHORT_ID(n),
    position: n,
    office_id: OFFICE(office),
    office_name: office,
    segment,
    status: done
      ? "executed"
      : n === 3
        ? "executing"
        : n === 4 || c5Approved
          ? "approved"
          : "draft",
    display,
    engagements: e,
    returns: r,
    binders: b,
    letters: e,
    invitations: n === 5 ? 61 : e,
    exceptions: n === 5 ? 3 : 0,
    approver,
    approved_at: done
      ? "2026-01-08T09:00:00-06:00"
      : n === 3 || n === 4
        ? "2026-01-09T09:00:00-06:00"
        : c5Approved
          ? "2026-01-12T10:21:00-06:00"
          : null,
    queued_after: c5Approved ? 4 : null,
    created_rows: done ? e : n === 3 ? 31 : 0,
    rows_hash: HASH,
    allowed_actions:
      n === 5 && !c5Approved ? ["approve", "exclude", "reassign"] : c5Approved ? ["withdraw"] : [],
  };
}

export function manifest(variant: Eng07Variant = "draft"): SeasonManifestOut {
  const cohorts = COHORTS.map((c) => cohort(c, variant));
  return {
    manifest_id: MANIFEST_ID,
    season_id: stableId("season:ty2025"),
    tax_year: 2025,
    version: 1,
    status: "ready",
    built_by: PEOPLE.gh,
    built_at: "2026-01-12T09:58:00-06:00",
    inputs_hash: HASH,
    tally: {
      engagements: 214,
      returns: 224,
      binders: 241,
      created: 126,
      cohorts_approved: variant === "approved" ? 5 : 4,
      cohorts: 6,
      exceptions: 3,
    },
    offices: [
      { office_id: OFFICE("Chicago"), office_name: "Chicago", returns: 98 },
      { office_id: OFFICE("Denver"), office_name: "Denver", returns: 64 },
      { office_id: OFFICE("New York"), office_name: "New York", returns: 62 },
    ],
    cohorts,
    asks: variant === "agentsOff" ? [] : [ASK],
    planner_available: variant !== "agentsOff",
    allowed_actions: ["export"],
  };
}

export const ASK: SeasonAskOut = {
  ask_id: stableId("season-ask:feld-binders"),
  question_code: "binder_choice",
  row_ids: [stableId("season-row:feld")],
  options: [
    { code: "use_newer", label: "One binder (recommended)" },
    { code: "use_both", label: "Two binders" },
  ],
  recommended_option: "use_newer",
  source: "agent",
  suggestion_id: null,
  answered_option: null,
  answered_by: null,
};

type R = readonly [
  key: string,
  name: string,
  forms: string[],
  p: SeasonPersonOut,
  rv: SeasonPersonOut,
  binder: string,
  requests: number,
  fee: string | null,
  consents: string[],
  signers: number,
  invitees: string[],
  codes: NonNullable<SeasonManifestRowOut["exception_codes"]>,
  sub: string | null,
];

const C5: readonly R[] = [
  [
    "feld",
    "Jonah & Claire Feld",
    ["1040"],
    PEOPLE.ko,
    PEOPLE.si,
    "1040 · prior-year (2024 return) · 7 requests",
    7,
    "4.00",
    ["use", "ai_disclosure"],
    2,
    ["Claire Feld (primary)", "Jonah Feld"],
    [],
    "K-1 from Ridgeline Property Partners, LP — internal handoff",
  ],
  [
    "iyer",
    "Priyanka & Sam Iyer",
    ["1040"],
    PEOPLE.ds,
    PEOPLE.ql,
    "prior-year · 16 requests",
    16,
    null,
    ["use", "ai_disclosure"],
    2,
    ["Priyanka Iyer", "Sam Iyer"],
    [],
    null,
  ],
  [
    "rao",
    "Sunil & Asha Rao",
    ["1040"],
    PEOPLE.ko,
    PEOPLE.ql,
    "prior-year · 12 requests",
    12,
    null,
    ["use", "ai_disclosure"],
    2,
    ["Sunil Rao"],
    [],
    null,
  ],
  [
    "osterberg",
    "Benjamin Osterberg",
    ["1040"],
    PEOPLE.rv,
    PEOPLE.np,
    "prior-year · 10 requests",
    10,
    null,
    ["use", "ai_disclosure"],
    1,
    ["Benjamin Osterberg"],
    ["assignee_seasonal_not_started"],
    "Preparer Remy Vidal (seasonal) starts Feb 2 — keep or reassign",
  ],
  [
    "ferris",
    "Morgan & Kai Ferris",
    ["1040"],
    PEOPLE.ds,
    PEOPLE.np,
    "prior-year · 12 requests",
    12,
    null,
    ["use", "ai_disclosure"],
    2,
    ["Morgan Ferris", "Kai Ferris"],
    [],
    null,
  ],
  [
    "kapoor",
    "Dev & Mira Kapoor",
    ["1040"],
    PEOPLE.ds,
    PEOPLE.ql,
    "prior-year · 14 requests",
    14,
    null,
    ["use", "ai_disclosure"],
    2,
    ["Dev Kapoor"],
    [],
    null,
  ],
  [
    "farouk",
    "Noor & Adam Farouk",
    ["1040"],
    PEOPLE.rv,
    PEOPLE.np,
    "prior-year · 11 requests",
    11,
    null,
    ["use", "ai_disclosure"],
    2,
    ["Noor Farouk"],
    ["assignee_seasonal_not_started"],
    "Preparer seasonal — starts Feb 2",
  ],
  [
    "barlow",
    "Estate of Eugene Barlow",
    ["1041"],
    PEOPLE.rv,
    PEOPLE.ql,
    "1041 · estate · 9 requests",
    9,
    null,
    ["use", "ai_disclosure"],
    1,
    ["Executor"],
    ["contact_bounced"],
    "Executor contact bounced Jan 9 — confirm email",
  ],
];

export function rows(cohort = 5): SeasonManifestRowOut[] {
  return C5.map(
    (
      [key, name, forms, p, rv, binder, requests, fee, consents, signers, invitees, codes, sub],
      i,
    ) => ({
      row_id: stableId(`season-row:${key}`),
      cohort_id: COHORT_ID(cohort),
      client_id: stableId(`client:${key}`),
      client_name: name,
      forms,
      preparer: p,
      reviewer: rv,
      signer: PEOPLE.dr,
      binder_summary: binder,
      request_count: requests,
      letter_kind: "renewal",
      fee_change_pct: fee,
      consent_purposes: consents,
      signers,
      invitees,
      exception_codes: codes,
      sub_line: sub,
      display: cohort === 3 ? (i < 5 ? "created" : "ready") : codes.length ? "check" : "ready",
      steps: [],
      row_version: 1,
      allowed_actions: codes.length ? ["reassign", "exclude"] : [],
    }),
  );
}
