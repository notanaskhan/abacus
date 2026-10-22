// P-08-T02: C5 v1.1 portal-half consumer fixture assertions (R-01, P-07, G-02; POR-01, POR-02).
// Each fixture is typed with the generated client, so a breaking change to a portal shape fails
// `tsc`; each is also checked against the OpenAPI document at run time. The home carries no firm
// status code, amount or agent field, at the type level and in the schema. Brightwater Hale,
// synthetic; shapes from docs/contracts/portal-identity.md §8. The sign-in, renew, preview and
// branding shapes are not served yet (DEC-139), so they have no generated type: their pytest half
// is backend/tests/contracts/c5_portal/.
import type {
  ContactMfaResetOut,
  ContactPortalStatusOut,
  InvitationStatus,
  MeMfaOut,
  MeOut,
  MePortalOut,
  PortalHomeOut,
  PortalHomeStageOut,
  PortalHomeTargetOut,
  PortalHomeTodoOut,
  PortalHomeWorkCardOut,
  PortalPreferencesIn,
  PortalPreferencesOut,
} from "@abacus/api-client";
import { type EnumCovered } from "@abacus/ui";
import { describe, expect, it } from "vitest";
import { validateResponse, validateSchema } from "../schema-check";

/** Every key of T and of every object type nested in it. */
type DeepKeys<T> = T extends readonly (infer U)[]
  ? DeepKeys<U>
  : T extends object
    ? { [K in keyof T & string]: K | DeepKeys<NonNullable<T[K]>> }[keyof T & string]
    : never;

// A firm status, an amount or an agent reference, by field name (POR-02 AVOID; contract §1).
type Forbidden =
  | "status"
  | `${string}_status`
  | "amount"
  | `${string}_amount`
  | "balance"
  | "materiality"
  | "currency"
  | "confidence"
  | "agent"
  | `agent_${string}`
  | `${string}_agent`
  | "run_id"
  | `${string}_run_id`
  | "drafted_by_run_id"
  | "allowed_actions";
type Clean<T> = [Extract<DeepKeys<T>, Forbidden>] extends [never] ? true : false;

const ID = {
  feld: "4e6a8c0e-2a4c-4e6a-8c0e-2a4c6e8a0c2e",
  copperleaf: "5f7b9d1f-3b5d-4f7b-9d1f-3b5d7f9b1d3f",
  meera: "6a8c0e2a-4c6e-4a8c-8e2a-4c6e8a0c2e4a",
  ridgeline: "7b9d1f3b-5d7f-4b9d-9f3b-5d7f9b1d3f5b",
  workItem: "8c0e2a4c-6e8a-4c0e-a4c6-e8a0c2e4a6c8",
  closeItem: "9d1f3b5d-7f9b-4d1f-b5d7-f9b1d3f5b7d9",
  binder: "0e2a4c6e-8a0c-4e2a-8c6e-a0c2e4a6c8e0",
  daniel: "1f3b5d7f-9b1d-4f3b-9d7f-b1d3f5b7d9f1",
  kevin: "2a4c6e8a-0c2e-4a4c-8e8a-c2e4a6c8e0a2",
  grace: "3b5d7f9b-1d3f-4b5d-9f9b-d3f5b7d9f1b3",
  contact: "4c6e8a0c-2e4a-4c6e-a0c2-e4a6c8e0a2c4",
  thread: "5d7f9b1d-3f5b-4d7f-b1d3-f5b7d9f1b3d5",
} as const;

const DOCUMENTS: PortalHomeTargetOut = { screen: "POR-03", params: {} };

const TAX_STAGES: PortalHomeStageOut[] = [
  { code: "gather_documents", state: "done" },
  { code: "prepare", state: "done" },
  { code: "review", state: "current" },
  { code: "sign_form_8879", state: "upcoming" },
  { code: "file", state: "upcoming" },
];

// GET /v1/portal/home?scope_id=… (Claire Feld, POR-02 a).
const CLAIRE: PortalHomeOut = {
  scope: {
    kind: "client",
    id: ID.feld,
    label: "Jonah & Claire Feld",
    sub: "Household · Brooklyn, NY",
    role_label: "Taxpayer",
  },
  todos: [
    {
      kind: "upload",
      count: 2,
      state: "open",
      detail: "Form 1095-C and your 2025 estimated payment confirmations",
      target: DOCUMENTS,
    },
    {
      kind: "answer",
      count: 3,
      state: "open",
      detail: "2 in your 2025 organizer · 1 from Kevin Osei",
      facts: { organizer_count: 2, from_team_count: 1 },
      target: { screen: "POR-05", params: {} },
    },
    { kind: "sign", count: 0, state: "none" },
    { kind: "deliverables", count: 2, state: "open", target: { screen: "POR-09", params: {} } },
  ],
  work_cards: [
    {
      work_item_id: ID.workItem,
      kind: "tax_return",
      title: "2025 Tax Return · Form 1040",
      sub: "Extended to Oct 15, 2026",
      pill: { code: "reviewing_return", variant: "state" },
      stages: TAX_STAGES,
      note_code: "waiting_on_k1",
      note_subject: "Ridgeline Property Partners, LP",
      note_date: "2026-09-15",
    },
  ],
  binder: { binder_id: ID.binder, done: 19, total: 21, sorted_count: 37 },
  team: [
    { user_id: ID.daniel, display_name: "Daniel Reyes", role_code: "partner_signs_return" },
    { user_id: ID.kevin, display_name: "Kevin Osei", role_code: "preparer_day_to_day" },
    { user_id: ID.grace, display_name: "Grace Holloway", role_code: "client_service" },
  ],
  earlier: [
    { kind: "extension_filed", date: "2026-04-14", facts: { tax_year: 2025, form: "4868" } },
    { kind: "engagement_letter_signed", date: "2026-02-02" },
    { kind: "return_filed", facts: { tax_year: 2024, form: "1040" } },
  ],
  recent_threads: [
    {
      thread_id: ID.thread,
      subject: "A question about digital assets",
      from_name: "Kevin Osei",
      at: "2026-09-11T15:10:00Z",
      unread: true,
    },
  ],
  first_visit: false,
  welcome_dismissed: true,
  all_done: false,
};

// Tess Moreno, Copperleaf (POR-02 d): the one overdue to-do, a close card with request counts.
const OVERDUE: PortalHomeTodoOut = {
  kind: "upload",
  count: 2,
  state: "overdue",
  due_date: "2026-09-05",
  detail: "Requested by Raj Malhotra for your August books.",
  target: { screen: "POR-11", params: {} },
};
const CLOSE: PortalHomeWorkCardOut = {
  work_item_id: ID.closeItem,
  kind: "close",
  title: "August 2026 Close",
  sub: "Monthly bookkeeping",
  pill: { code: "reconciling_accounts", variant: "state" },
  stages: [
    { code: "requests", state: "current", facts: { done: 7, total: 9 } },
    { code: "reconcile", state: "upcoming" },
    { code: "review", state: "upcoming" },
    { code: "statements", state: "upcoming" },
  ],
};

describe("the portal home as R-01 and POR-02 read it", () => {
  it("serves Claire's home in the schema, footing Upload 2 and binder 19 of 21 with 37 sorted", () => {
    expect(validateResponse("get", "/v1/portal/home", CLAIRE)).toEqual([]);
    expect(CLAIRE.todos?.[0]?.count).toBe(2);
    expect(CLAIRE.binder).toEqual({ binder_id: ID.binder, done: 19, total: 21, sorted_count: 37 });
  });

  it("carries no firm status, amount or agent field anywhere in the home", () => {
    const clean: true = true satisfies Clean<PortalHomeOut>;
    expect(clean).toBe(true);
  });

  it("refuses a firm status word, an amount or an agent field at run time", () => {
    const card = CLAIRE.work_cards?.[0];
    expect(validateSchema("PortalHomeWorkCardOut", { ...card, status: "in_review" })).toHaveLength(
      1,
    );
    expect(
      validateSchema("PortalHomePillOut", { code: "in_review", variant: "state" }),
    ).toHaveLength(1);
    expect(
      validateSchema("PortalHomeBinderOut", { ...CLAIRE.binder, amount: "1200.00" }),
    ).toHaveLength(1);
    expect(
      validateSchema("PortalHomeTeamMemberOut", {
        user_id: ID.kevin,
        display_name: "Agent",
        role_code: "agent",
      }),
    ).toHaveLength(1);
  });

  it("marks only the past-due to-do overdue and keeps close requests as stage facts", () => {
    expect(validateSchema("PortalHomeTodoOut", OVERDUE)).toEqual([]);
    expect(validateSchema("PortalHomeWorkCardOut", CLOSE)).toEqual([]);
    const pill: PortalHomeWorkCardOut["pill"]["variant"][] = ["state", "success", "neutral"];
    for (const variant of pill) {
      expect(validateSchema("PortalHomePillOut", { code: "filed_and_accepted", variant })).toEqual(
        [],
      );
    }
    expect(
      validateSchema("PortalHomePillOut", { code: "filed_and_accepted", variant: "red" }),
    ).toHaveLength(1);
  });

  it("lists Meera's K-1 as released or not, never by the firm's package status", () => {
    const meera: PortalHomeOut = {
      scope: {
        kind: "client",
        id: ID.meera,
        label: "Meera Shah",
        sub: "Individual",
        role_label: "Taxpayer",
      },
      my_k1s: [
        {
          k1_package_id: ID.ridgeline,
          label: "Ridgeline Property Partners, LP · 2025 Schedule K-1",
          released: false,
          expected_by: "2026-09-15",
        },
      ],
      first_visit: false,
      welcome_dismissed: true,
      all_done: false,
    };
    expect(validateResponse("get", "/v1/portal/home", meera)).toEqual([]);
    expect(
      validateSchema("PortalHomeK1Out", { ...meera.my_k1s?.[0], status: "draft" }),
    ).toHaveLength(1);
  });

  it("stores the welcome dismissal per scope with a version", () => {
    const body: PortalPreferencesIn = { scope_id: ID.feld, welcome_dismissed: true, version: 0 };
    const saved: PortalPreferencesOut = {
      scope_id: ID.feld,
      welcome_dismissed: true,
      welcome_dismissed_at: "2026-02-02T15:04:00Z",
      version: 1,
    };
    expect(validateSchema("PortalPreferencesIn", body)).toEqual([]);
    expect(validateResponse("put", "/v1/portal/preferences", saved)).toEqual([]);
    expect(validateSchema("PortalPreferencesIn", { ...body, user_id: ID.grace })).toHaveLength(1);
  });
});

describe("the portal shell on /v1/me", () => {
  const tess: MePortalOut = {
    shell: "full",
    scopes: [
      {
        kind: "client_entity",
        id: ID.copperleaf,
        label: "Copperleaf Coffee Roasters, Inc.",
        role_label: "Owner",
      },
    ],
    nav: ["home", "documents", "questions", "approvals", "sign", "messages", "deliverables"],
    landing: "home",
  };
  const mfa: MeMfaOut = { enrolled: true, required: true, trusted_until: null };

  it("adds portal and mfa without changing the rest of MeOut", () => {
    const me: Pick<MeOut, "portal" | "mfa"> = { portal: tess, mfa };
    expect(validateSchema("MePortalOut", me.portal)).toEqual([]);
    expect(validateSchema("MeMfaOut", me.mfa)).toEqual([]);
    const optional: Pick<MeOut, "portal" | "mfa"> = {};
    expect(optional).toEqual({});
  });

  it("has no bell in the nav and routes a third party to requests", () => {
    expect(
      validateSchema("MePortalOut", { ...tess, nav: ["home", "notifications"] }),
    ).toHaveLength(1);
    expect(
      validateSchema("MePortalOut", { ...tess, shell: "limited", landing: "requests" }),
    ).toEqual([]);
  });

  it("never carries the second-step factor", () => {
    expect(validateSchema("MeMfaOut", { ...mfa, totp_secret: "JBSWY3DPEHPK3PXP" })).toHaveLength(
      1,
    );
  });
});

describe("firm-side recovery as P-07 (CLI-04) and G-02 (ADM-06) read it", () => {
  it("answers an unlock in the invitation status words", () => {
    const covered: true = true satisfies EnumCovered<"invitation", InvitationStatus>;
    expect(covered).toBe(true);
    const unlocked: ContactPortalStatusOut = {
      client_id: ID.feld,
      contact_id: ID.contact,
      portal_status: "active",
      locked_until: null,
    };
    expect(
      validateResponse(
        "post",
        "/v1/clients/{client_id}/contacts/{contact_id}/portal-unlock",
        unlocked,
      ),
    ).toEqual([]);
    expect(
      validateSchema("ContactPortalStatusOut", { ...unlocked, portal_status: "unlocked" }),
    ).toHaveLength(1);
  });

  it("answers an MFA reset with counts and a time, never a factor", () => {
    const reset: ContactMfaResetOut = {
      client_id: ID.copperleaf,
      contact_id: ID.contact,
      mfa_enrolled: false,
      trusted_devices_revoked: 1,
      reset_at: "2026-09-14T16:02:00Z",
    };
    expect(
      validateResponse("post", "/v1/clients/{client_id}/contacts/{contact_id}/mfa-reset", reset),
    ).toEqual([]);
  });
});

describe("white label", () => {
  it("names no vendor in any portal fixture", () => {
    const text = JSON.stringify([CLAIRE, OVERDUE, CLOSE]).toLowerCase();
    expect(text).not.toContain("accrued");
  });
});
