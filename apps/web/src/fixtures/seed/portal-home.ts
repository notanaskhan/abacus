// The portal's E0 rows (P-08-T08; docs/contracts/portal-identity.md §8; POR-01 and POR-02 screen
// contracts): Brightwater Hale's branding, each portal persona's `/v1/me` portal shell, and the
// POR-02 homes a (Claire Feld), b (her first visit, Feb 2), c (all set), d (Tess Moreno, Copperleaf,
// overdue) and e (Meera Shah's role union). Names and figures are the handoff's and the blueprint's;
// typed with the generated client so a schema change breaks the build. g and h (R2 waves 6 and 7:
// Granite Peak statements review, Tessellate SOC 2) arrive with their epochs.

import type { MePortalOut, PortalHomeOut, PortalHomeWorkCardOut } from "@abacus/api-client";
import type { PortalBrandingOut } from "../../app-core/portal-contracts";
import { COPPERLEAF_CLOSE } from "./client-rows";
import { stableId } from "./prng";

/** `GET /v1/portal/branding` on brightwaterhale.<neutral-portal-domain> (POR-01 a–g). */
export const BRIGHTWATER_BRANDING: PortalBrandingOut = {
  firm_name: "Brightwater Hale LLP",
  portal_name: "Brightwater Hale",
  logo_url: null,
  address_line: "Brightwater Hale LLP · 311 West Brannock Street, Chicago, IL",
  help_url: "https://www.brightwaterhale.example/help",
  privacy_url: "https://www.brightwaterhale.example/privacy",
  support_contact_name: "Grace Holloway",
  secured_footer: false,
  sign_in: { methods: ["email_code"], mfa_floor: ["owner", "signer", "approver"] },
  maintenance_banner: null,
};

/** The same shape for a host that names no firm: no firm mark, name, address or person. */
export const NEUTRAL_BRANDING: PortalBrandingOut = {
  firm_name: null,
  portal_name: null,
  logo_url: null,
  address_line: null,
  help_url: null,
  privacy_url: null,
  support_contact_name: null,
  secured_footer: false,
  sign_in: { methods: ["email_code"], mfa_floor: [] },
  maintenance_banner: null,
};

/** The fixture code for every persona (fixture only; real codes are random, P-08 §5.4). */
export const FIXTURE_CODE = "481027";
/** f's mistyped code, one digit pair swapped. */
export const MISTYPED_CODE = "481072";
/** c and c′ (P-08-T19): the fixture authenticator shows the canvas's code too (fixtures only;
 * a real TOTP changes every 30 seconds). */
export const FIXTURE_TOTP = FIXTURE_CODE;
/** c′'s 8 backup codes (16 Crockford base32 characters in four groups, as the BFF issues them;
 * fixture values, never a real code). c's backup-code path accepts the first, once. */
export const FIXTURE_BACKUP_CODES: readonly string[] = [
  "7KQ2-M9XD-4HTP-WB3R",
  "N6VC-2YJF-8RKS-QD5E",
  "3PHM-WX7A-KD9N-T2GB",
  "Y4RE-6CJZ-MQ8V-HS1K",
  "D9TB-5NWF-2XKP-R7MA",
  "Q2GS-H8VY-6EJD-4NCT",
  "B5MK-R3XP-9WDT-ZJ6H",
  "F8NA-4QYC-7SGM-2EVR",
];

const id = (label: string): string => stableId(`portal:${label}`);

export const SCOPE_IDS = {
  feld: id("scope:feld"),
  copperleaf: id("scope:copperleaf"),
  meera: id("scope:meera-shah"),
  ridgelineK1: id("scope:ridgeline-k1-meera"),
} as const;

const FULL_NAV: MePortalOut["nav"] = [
  "home",
  "documents",
  "questions",
  "sign",
  "messages",
  "deliverables",
];

/** `GET /v1/me` → `portal`, by persona (DEC-129: the union of the person's grants). */
export const PORTAL_SHELLS: Readonly<Record<string, MePortalOut>> = {
  "claire-feld": {
    shell: "full",
    scopes: [
      { kind: "client", id: SCOPE_IDS.feld, label: "Jonah & Claire Feld", role_label: "Taxpayer" },
    ],
    nav: FULL_NAV,
    landing: "home",
  },
  "tess-moreno": {
    shell: "full",
    scopes: [
      {
        kind: "client_entity",
        id: SCOPE_IDS.copperleaf,
        label: "Copperleaf Coffee Roasters, Inc.",
        role_label: "Owner",
      },
    ],
    nav: ["home", "documents", "questions", "approvals", "sign", "messages", "deliverables"],
    landing: "home",
  },
  "meera-shah": {
    shell: "full",
    scopes: [
      { kind: "client", id: SCOPE_IDS.meera, label: "Meera Shah", role_label: "Taxpayer" },
      {
        kind: "k1_package",
        id: SCOPE_IDS.ridgelineK1,
        label: "Ridgeline Property Partners, LP",
        role_label: "K-1 recipient",
      },
    ],
    nav: FULL_NAV,
    landing: "home",
  },
  "sam-ortiz": {
    shell: "limited",
    scopes: [
      {
        kind: "engagement",
        id: id("scope:northwind-401k-keystone"),
        label: "Northwind Robotics 401(k) Plan",
        role_label: "Recordkeeper",
      },
    ],
    nav: [],
    landing: "requests",
  },
  // R-01-T05: POR-03 i (Dana's own Northwind requests), POR-04 e and f (the Copperleaf
  // contributor and Ridgeline's general partner) and POR-14 d (Harborline's room).
  "dana-kowalski": {
    shell: "full",
    scopes: [
      {
        kind: "engagement",
        id: id("scope:northwind-401k"),
        label: "Northwind Robotics 401(k) Plan",
        role_label: "Plan administrator",
      },
    ],
    nav: FULL_NAV,
    landing: "home",
  },
  "ben-ashby": {
    shell: "full",
    scopes: [
      {
        kind: "client_entity",
        id: SCOPE_IDS.copperleaf,
        label: "Copperleaf Coffee Roasters, Inc.",
        role_label: "Contributor",
      },
    ],
    nav: ["home", "documents", "questions", "approvals", "sign", "messages", "deliverables"],
    landing: "home",
  },
  "owen-calder": {
    shell: "full",
    scopes: [
      {
        kind: "client_entity",
        id: id("scope:ridgeline"),
        label: "Ridgeline Property Partners, LP",
        role_label: "Owner",
      },
    ],
    nav: ["home", "documents", "questions", "approvals", "sign", "messages", "deliverables"],
    landing: "home",
  },
  "harborline-certifications": {
    shell: "limited",
    scopes: [
      {
        kind: "engagement",
        id: id("scope:northwind-401k-harborline"),
        label: "Northwind Robotics 401(k) Plan",
        role_label: "Custodian",
      },
    ],
    nav: [],
    landing: "requests",
  },
};

/** Personas whose verified code meets the firm's MFA floor (an owner, signer or approver grant). */
export const MFA_FLOOR_PERSONAS: ReadonlySet<string> = new Set(["tess-moreno"]);

const TEAM_FELD: NonNullable<PortalHomeOut["team"]> = [
  {
    user_id: stableId("user:daniel-reyes"),
    display_name: "Daniel Reyes",
    role_code: "partner_signs_return",
  },
  {
    user_id: stableId("user:samuel-ito"),
    display_name: "Samuel Ito",
    role_code: "manager_reviews_return",
  },
  {
    user_id: stableId("user:kevin-osei"),
    display_name: "Kevin Osei",
    role_code: "preparer_day_to_day",
  },
  {
    user_id: stableId("user:grace-holloway"),
    display_name: "Grace Holloway",
    role_code: "client_service",
  },
];

const FELD_RETURN: PortalHomeWorkCardOut = {
  work_item_id: id("work-item:feld-1040-2025"),
  kind: "tax_return",
  title: "2025 Tax Return · Form 1040",
  sub: "Extended to Oct 15, 2026",
  pill: { code: "reviewing_return", variant: "state" },
  stages: [
    { code: "gather_documents", state: "done" },
    { code: "prepare", state: "done" },
    { code: "review", state: "current" },
    { code: "sign_form_8879", state: "upcoming" },
    { code: "file", state: "upcoming" },
  ],
  note_code: "waiting_on_k1",
  note_subject: "Ridgeline Property Partners, LP",
  note_date: "2026-09-15",
};

/** The Feld 2025 binder as POR-02 counts it (blueprint 01 §9.5). */
export const FELD_BINDER = { done: 19, total: 21, sorted: 37 } as const;
/** "Answer 3 questions": 2 in the organizer + 1 from the team. */
export const FELD_QUESTIONS = { organizer: 2, fromTeam: 1 } as const;

/** POR-02 a: Claire Feld at E0. Upload 2 is the binder's Intake 2 (the seed's two open requests). */
export function claireHome(openUploads: number): PortalHomeOut {
  return {
    scope: {
      kind: "client",
      id: SCOPE_IDS.feld,
      label: "Jonah & Claire Feld",
      sub: "Household · Brooklyn, NY",
      role_label: "Taxpayer",
    },
    todos: [
      {
        kind: "upload",
        count: openUploads,
        state: "open",
        detail: "Form 1095-C and your 2025 estimated payment confirmations",
        target: { screen: "POR-03", params: {} },
      },
      {
        kind: "answer",
        count: FELD_QUESTIONS.organizer + FELD_QUESTIONS.fromTeam,
        state: "open",
        detail: "2 in your 2025 organizer · 1 from Kevin Osei",
        facts: {
          organizer_count: FELD_QUESTIONS.organizer,
          from_team_count: FELD_QUESTIONS.fromTeam,
        },
        target: { screen: "POR-05", params: {} },
      },
      { kind: "sign", count: 0, state: "none" },
      { kind: "deliverables", count: 2, state: "open", target: { screen: "POR-09", params: {} } },
    ],
    work_cards: [FELD_RETURN],
    binder: {
      binder_id: id("binder:feld-2025"),
      done: FELD_BINDER.done,
      total: FELD_BINDER.total,
      sorted_count: FELD_BINDER.sorted,
    },
    team: TEAM_FELD,
    earlier: [
      { kind: "extension_filed", date: "2026-04-14", facts: { tax_year: 2025, form: "4868" } },
      { kind: "engagement_letter_signed", date: "2026-02-02" },
      { kind: "return_filed", facts: { tax_year: 2024, form: "1040" } },
    ],
    recent_threads: [],
    first_visit: false,
    welcome_dismissed: true,
    all_done: false,
  };
}

/** POR-02 b: Claire's first visit, Mon Feb 2, 2026. */
export function claireFirstVisit(): PortalHomeOut {
  const base = claireHome(0);
  return {
    ...base,
    todos: [
      {
        kind: "sign",
        count: 3,
        state: "open",
        detail: "Sign your engagement letter and two §7216 consents",
        target: { screen: "POR-06", params: {} },
      },
      {
        kind: "upload",
        count: FELD_BINDER.total,
        state: "open",
        detail: "Upload your 2025 documents (21 requested)",
        target: { screen: "POR-03", params: {} },
      },
    ],
    work_cards: [
      {
        ...FELD_RETURN,
        sub: "Due Apr 15, 2026",
        pill: { code: "getting_started", variant: "state" },
        stages: [
          { code: "gather_documents", state: "current" },
          { code: "prepare", state: "upcoming" },
          { code: "review", state: "upcoming" },
          { code: "sign_form_8879", state: "upcoming" },
          { code: "file", state: "upcoming" },
        ],
        note_code: null,
        note_subject: null,
        note_date: null,
      },
    ],
    binder: {
      binder_id: id("binder:feld-2025"),
      done: 0,
      total: FELD_BINDER.total,
      sorted_count: 0,
    },
    recent_threads: [
      {
        thread_id: id("thread:feld-welcome"),
        subject: "Welcome to your client portal",
        from_name: "Grace Holloway",
        at: "2026-02-02T15:04:00Z",
        unread: true,
      },
    ],
    earlier: [{ kind: "return_filed", facts: { tax_year: 2024, form: "1040" } }],
    first_visit: true,
    welcome_dismissed: false,
  };
}

/** POR-02 c: nothing is waiting on Claire. */
export function claireAllDone(): PortalHomeOut {
  const base = claireHome(0);
  return {
    ...base,
    todos: (base.todos ?? []).map((t) => ({ ...t, count: 0, state: "none" as const })),
    all_done: true,
  };
}

/** POR-02 d: Tess Moreno, Copperleaf: the one past-due to-do and the August close (7 of 9). */
export function tessHome(): PortalHomeOut {
  return {
    scope: {
      kind: "client_entity",
      id: SCOPE_IDS.copperleaf,
      label: "Copperleaf Coffee Roasters, Inc.",
      sub: "S corporation · Denver, CO",
      role_label: "Owner",
    },
    todos: [
      {
        kind: "upload",
        count: COPPERLEAF_CLOSE.requests - COPPERLEAF_CLOSE.received,
        state: "overdue",
        due_date: "2026-09-05",
        detail: "Requested by Raj Malhotra for your August books.",
        target: { screen: "POR-11", params: {} },
      },
      { kind: "answer", count: 3, state: "open", target: { screen: "POR-05", params: {} } },
      { kind: "reconnect", count: 1, state: "open", detail: "American Express" },
      { kind: "approve", count: 0, state: "none" },
    ],
    work_cards: [
      {
        work_item_id: id("work-item:copperleaf-close-2026-08"),
        kind: "close",
        title: "August 2026 Close",
        sub: "Monthly bookkeeping",
        pill: { code: "reconciling_accounts", variant: "state" },
        stages: [
          {
            code: "requests",
            state: "current",
            facts: { done: COPPERLEAF_CLOSE.received, total: COPPERLEAF_CLOSE.requests },
          },
          { code: "reconcile", state: "upcoming" },
          { code: "review", state: "upcoming" },
          { code: "statements", state: "upcoming" },
        ],
      },
      {
        work_item_id: id("work-item:copperleaf-1120s-2025"),
        kind: "tax_return",
        title: "TY2025 Form 1120-S",
        pill: { code: "filed_and_accepted", variant: "success" },
      },
    ],
    team: [
      { user_id: stableId("user:priya-raman"), display_name: "Priya Raman", role_code: "partner" },
      {
        user_id: stableId("user:raj-malhotra"),
        display_name: "Raj Malhotra",
        role_code: "close_preparer",
      },
      {
        user_id: stableId("user:grace-holloway"),
        display_name: "Grace Holloway",
        role_code: "client_service",
      },
    ],
    first_visit: false,
    welcome_dismissed: true,
    all_done: false,
  };
}

/** POR-02 e: Meera Shah's own return and her Ridgeline K-1, released or not, nothing else of it. */
export function meeraHome(): PortalHomeOut {
  return {
    scope: {
      kind: "client",
      id: SCOPE_IDS.meera,
      label: "Meera Shah",
      sub: "Individual",
      role_label: "Taxpayer",
    },
    work_cards: [
      {
        work_item_id: id("work-item:meera-1040-2025"),
        kind: "tax_return",
        title: "2025 Tax Return · Form 1040",
        pill: { code: "preparing_return", variant: "state" },
        note_code: "waiting_on_your_k1",
        note_subject: "Ridgeline Property Partners, LP",
      },
    ],
    my_k1s: [
      {
        k1_package_id: SCOPE_IDS.ridgelineK1,
        label: "Ridgeline Property Partners, LP · 2025 Schedule K-1",
        released: false,
        expected_by: "2026-09-15",
      },
    ],
    team: [
      {
        user_id: stableId("user:neil-ashcroft"),
        display_name: "Neil Ashcroft",
        role_code: "partner",
      },
      { user_id: stableId("user:lena-park"), display_name: "Lena Park", role_code: "preparer" },
      {
        user_id: stableId("user:grace-holloway"),
        display_name: "Grace Holloway",
        role_code: "client_service",
      },
    ],
    first_visit: false,
    welcome_dismissed: true,
    all_done: false,
  };
}
