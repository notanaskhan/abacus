// CLI-07's acceptance records (P-07-T46; docs/screens/CLI-07.md): `GET …/acceptance` as the live
// route answers it (`AcceptanceRecordOut`, P-07-T35), the engagements the records belong to
// (`EngagementRecordOut`) and their teams (`TeamRosterMemberOut`), typed with the generated
// client. Names, titles and text are verbatim from the CLI-07 handoff (spec.md a–f, revision R2 g).
// Production flags are human-prepared (DEC-64, SPEC-332 AC-2): Samuel Ito authored Thornbury's,
// Hannah Leclerc Meridian's and Granite Peak's. Sources are object references only.
//
//   Thornbury  "Form 706 & estate Form 1041", Tax engagements v2, Moderate, three flags (a–e)
//   Meridian   continuance "FY2026 FS audit", Audit engagements v2, Low, one flag (f)
//   Granite    continuance "FY2027 FS audit", Draft on Oct 1, the responsiveness flag (g)
//
// A section's rail line and its "Clear sections" line are its answers (`summary`, `detail`):
// the questionnaire is the firm's database template, never screen copy (docs/screens/CLI-07.md).

import type {
  AcceptanceConditionOut,
  AcceptanceFlagOut,
  AcceptanceRecordOut,
  AcceptanceSectionOut,
  EngagementRecordOut,
  ManualCheckOut,
  TeamRosterMemberOut,
} from "@abacus/api-client";
import { entityIdOf, slugOfClient } from "./clients";
import type { EngagementRecordFixture } from "./engagement-records";
import { slugOf } from "./people";
import { stableId } from "./prng";

export function personId(name: string): string {
  return stableId(`user:${slugOf(name)}`);
}

export const DANIEL = "Daniel Reyes";
export const SAMUEL = "Samuel Ito";
export const GRACE = "Grace Holloway";
export const MARGARET = "Margaret Okonkwo";
export const HANNAH = "Hannah Leclerc";

/** Instants (UTC) of the records' events; CT is UTC−5 in September and October 2026. */
export const AT = {
  /** Fri Sep 11, 4:02 PM CT: Samuel Ito's flags. */
  thornburyFlags: "2026-09-11T21:02:00Z",
  /** Fri Sep 11, 4:05 PM CT: Samuel asks Grace Holloway for the fee check. */
  feeCheckAsked: "2026-09-11T21:05:00Z",
  /** Fri Sep 11, 4:40 PM CT: Grace confirms it. */
  feeCheckDone: "2026-09-11T21:40:00Z",
  /** Fri Sep 11, 5:00 PM CT: sent to Daniel Reyes. */
  thornburySent: "2026-09-11T22:00:00Z",
  /** Mon Sep 14, 9:46 AM CT: accepted with conditions (d). */
  accepted: "2026-09-14T14:46:00Z",
  /** Mon Sep 14, 9:40 AM CT: declined (e). */
  declined: "2026-09-14T14:40:00Z",
  /** Fri Sep 11, 4:30 PM CT: Meridian's flag. */
  meridianFlag: "2026-09-11T21:30:00Z",
  meridianSent: "2026-09-11T22:15:00Z",
  /** Thu Oct 1, 10:20 AM CT: Granite Peak's responsiveness flag. */
  graniteFlag: "2026-10-01T15:20:00Z",
  graniteCheckAsked: "2026-10-01T15:25:00Z",
} as const;

// ---- engagements and teams --------------------------------------------------------------------

function engagement(
  key: string,
  client: string,
  name: string,
  over: Partial<EngagementRecordOut>,
): EngagementRecordOut {
  return {
    id: stableId(`engagement:acceptance:${key}`),
    name,
    client_id: stableId(`client:${slugOfClient(client)}`),
    client_name: client,
    client_entity_id: entityIdOf(slugOfClient(client), client),
    client_entity_name: client,
    type: "tax_compliance",
    service_line: "tax",
    status: "prospect",
    period_label: null,
    fiscal_period_start: "2026-01-01",
    fiscal_period_end: "2026-12-31",
    bands: [],
    contacts: [],
    letter: { status: "not_signed", signed_count: 0, signer_count: 0 },
    gates: [{ gate: "G1", met: false }],
    tab_counts: { work_items: 0, team: 3 },
    read_only_reason: null,
    version: 1,
    allowed_actions: ["engagement.read_metadata", "engagement.read"],
    ...over,
  };
}

function member(name: string, role: TeamRosterMemberOut["role"]): TeamRosterMemberOut {
  return {
    user_id: personId(name),
    display_name: name,
    role,
    budget_hours: null,
    shown_on_portal: false,
    independence: "confirmed",
  };
}

export const THORNBURY_CLIENT = "Estate of Walter Thornbury";
export const MERIDIAN_CLIENT = "Meridian Tool & Die, Inc.";
export const GRANITE_CLIENT = "Granite Peak Outdoor Supply, Inc.";

export function thornburyEngagement(
  status: EngagementRecordOut["status"] = "prospect",
): EngagementRecordFixture {
  return {
    record: engagement("thornbury", THORNBURY_CLIENT, "Form 706 & estate Form 1041", {
      status,
      period_label: "2026–2027",
      fiscal_period_end: "2027-01-31",
    }),
    workItems: [],
    acceptanceDecidedAt: null,
    team: [
      member(DANIEL, "engagement_partner"),
      member(SAMUEL, "manager"),
      member(GRACE, "client_service"),
    ],
  };
}

export function meridianEngagement(): EngagementRecordFixture {
  return {
    record: engagement("meridian-fy2026", MERIDIAN_CLIENT, "FY2026 FS audit", {
      type: "fs_audit",
      service_line: "audit",
      period_label: "FY2026",
    }),
    workItems: [],
    acceptanceDecidedAt: null,
    team: [member(MARGARET, "engagement_partner"), member(HANNAH, "manager")],
  };
}

export function graniteEngagement(): EngagementRecordFixture {
  return {
    record: engagement("granite-fy2027", GRANITE_CLIENT, "FY2027 FS audit", {
      type: "fs_audit",
      service_line: "audit",
      period_label: "FY2027",
      fiscal_period_start: "2026-07-01",
      fiscal_period_end: "2027-06-30",
    }),
    workItems: [],
    acceptanceDecidedAt: null,
    team: [
      member(MARGARET, "engagement_partner"),
      member(HANNAH, "manager"),
      member(GRACE, "client_service"),
    ],
  };
}

// ---- sections ---------------------------------------------------------------------------------

function section(
  code: string,
  title: string,
  answer_state: AcceptanceSectionOut["answer_state"],
  summary: string | null,
  detail: string | null = null,
): AcceptanceSectionOut {
  const answers: Record<string, string> = {};
  if (summary !== null) answers.summary = summary;
  if (detail !== null) answers.detail = detail;
  return {
    code,
    title,
    answer_state,
    answers,
    manual_check: null,
    version: answer_state === "pending" && summary === null ? 0 : 1,
  };
}

function feeCheck(asked: string, of: string, by: string, done: string | null): ManualCheckOut {
  return {
    section_code: "fees",
    requested_at: asked,
    requested_by: personId(by),
    requested_of: personId(of),
    completed_at: done,
    completed_by: done === null ? null : personId(of),
    note: null,
  };
}

/** Thornbury's nine sections; `feesOpen` is b, before Grace Holloway's check. */
function thornburySections(feesOpen: boolean): AcceptanceSectionOut[] {
  const fees = feesOpen
    ? {
        ...section(
          "fees",
          "Fees & collectability",
          "manual_check_open",
          "Manual check · estate not yet in CCH Axcess Practice",
          "The estate has no billing account in CCH Axcess Practice yet, so unpaid fees on the Walter Thornbury account need a manual check.",
        ),
        manual_check: feeCheck(AT.feeCheckAsked, GRACE, SAMUEL, null),
      }
    : {
        ...section(
          "fees",
          "Fees & collectability",
          "manual_check_done",
          "Manual check · GH · no unpaid fees",
          "CCH Axcess Practice shows no unpaid invoices on the Walter Thornbury account; the estate has no billing account there yet, so Grace Holloway confirmed it manually (Sep 11)",
        ),
        manual_check: feeCheck(AT.feeCheckAsked, GRACE, SAMUEL, AT.feeCheckDone),
      };
  return [
    section(
      "profile",
      "Engagement profile",
      "complete",
      "Complete · SI",
      "Form 706, estate Form 1041, final Form 1040 and Form 56 · tax services only, no attest relationship (independence not applicable) · §7216 use and AI-disclosure consents (2 documents) to be signed by the executor",
    ),
    section(
      "integrity",
      "Executor integrity screening",
      "complete",
      "No matches · OFAC & adverse media",
      "OFAC SDN and adverse media on Paul Thornbury and the estate — no matches (Sep 11)",
    ),
    section("authority", "Authority & documents", "flag", "1 flag · letters of office missing"),
    section("scope", "Scope & complexity", "flag", "1 flag · Form 706 required"),
    section(
      "identification",
      "Client identification & conflicts",
      "flag",
      "1 flag · executor is also a beneficiary",
    ),
    section(
      "prior",
      "Prior-year history",
      "complete",
      "No issues found",
      "Walter Thornbury's TY2024 Form 1040 filed on time; no open notices; TY2025 Form 1040 in Gathering (BN / YK)",
    ),
    fees,
    section(
      "competence",
      "Competence & capacity",
      "complete",
      "Estates & trusts: DR, SI",
      "estate and trust returns in the current year — Calloway Family Trust (1041), Estate of Eugene Barlow (1041); DR and SI have estate-tax experience",
    ),
    section("conclusion", "Conclusion", "pending", null),
  ];
}

/** c: the pre-screen has answered 4 of the 9 sections. */
function screeningSections(): AcceptanceSectionOut[] {
  return thornburySections(true).map((s, i) =>
    i < 4 ? s : { ...s, answer_state: "pending", answers: {}, manual_check: null, version: 0 },
  );
}

// ---- flags ------------------------------------------------------------------------------------

function ref(kind: "evidence_version" | "request_item", label: string) {
  return { kind, id: stableId(`${kind}:${label}`) };
}

function thornburyFlags(): AcceptanceFlagOut[] {
  const by = personId(SAMUEL);
  return [
    {
      id: stableId("acceptance-flag:thornbury:form-706"),
      title: "Form 706 is required",
      severity: "medium",
      body: "The executor's asset summary puts the gross estate at about $16.4M, above the 2026 basic exclusion amount of $15,000,000. The return is due Nov 2, 2026 (9 months after the Feb 2, 2026 date of death). Form 4768 gives an automatic 6-month extension to file, to May 3, 2027; extending time to pay needs a separate request. Valuations for non-marketable assets may need a qualified appraiser.",
      sources: [
        ref("evidence_version", "thornbury:asset-summary"),
        ref("evidence_version", "knowledge:2026-basic-exclusion"),
      ],
      authored_by: by,
      authored_at: AT.thornburyFlags,
    },
    {
      id: stableId("acceptance-flag:thornbury:authority"),
      title: "Executor authority is not yet evidenced",
      severity: "medium",
      body: "No letters of office from the Circuit Court of Cook County are in Files. The intake answer says letters are pending. Without them we cannot confirm Paul Thornbury can engage us or sign for the estate. (Walter's 2025 Form 1040 letter, signed Apr 14, relied on Paul as the executor named in the will; the estate engagement needs the court's appointment.)",
      sources: [ref("request_item", "thornbury:intake-q7")],
      authored_by: by,
      authored_at: AT.thornburyFlags,
    },
    {
      id: stableId("acceptance-flag:thornbury:identification"),
      title: "Client identification — the estate, not the beneficiaries",
      severity: "low",
      body: "Paul Thornbury is the executor and also a beneficiary. Our client is the estate acting through him. Other beneficiaries are not clients, and their interests may differ (Circular 230 §10.29). The engagement letter should say so.",
      sources: [ref("request_item", "thornbury:intake-q4")],
      authored_by: by,
      authored_at: AT.thornburyFlags,
    },
  ];
}

/** d's three conditions, owned by Samuel Ito and open. */
export const THORNBURY_CONDITIONS = [
  "Letters of office on file before the letter is signed.",
  "Letter names the client as the estate, acting through the executor.",
  "Form 56 filed with the IRS.",
] as const;

function conditions(texts: readonly string[], owner: string): AcceptanceConditionOut[] {
  return texts.map((text, i) => ({
    id: stableId(`acceptance-condition:thornbury:${String(i + 1)}`),
    text,
    assignee_user_id: personId(owner),
    due_on: null,
    completed_at: null,
    completed_by: null,
  }));
}

// ---- records ----------------------------------------------------------------------------------

export type ThornburyStage = "screening" | "draft" | "awaiting" | "accepted" | "declined";

export function thornburyRecord(stage: ThornburyStage): AcceptanceRecordOut {
  const engagementId = thornburyEngagement().record.id;
  const sent = stage !== "screening" && stage !== "draft";
  const base: AcceptanceRecordOut = {
    id: stableId("acceptance-record:thornbury"),
    engagement_id: engagementId,
    client_id: stableId(`client:${slugOfClient(THORNBURY_CLIENT)}`),
    kind: "new_engagement_existing_client",
    status: "awaiting_partner",
    template_version_id: stableId("acceptance-template:tax-engagements:v2"),
    template_name: "Tax engagements v2",
    prepared_by: personId(SAMUEL),
    risk_rating: "moderate",
    sections: thornburySections(stage === "draft"),
    flags: thornburyFlags(),
    decision: null,
    conditions: [],
    risk_partner_review: null,
    prior: null,
    sent_to_partner_at: sent ? AT.thornburySent : null,
    sent_to_partner_by: sent ? personId(SAMUEL) : null,
    version: sent ? 14 : 12,
    allowed_actions: [],
  };
  switch (stage) {
    case "screening":
      return {
        ...base,
        status: "pre_screening",
        risk_rating: null,
        sections: screeningSections(),
        flags: [],
        version: 4,
      };
    case "draft":
      return { ...base, status: "draft" };
    case "awaiting":
      return base;
    case "accepted":
      return {
        ...base,
        status: "decided",
        decision: {
          option: "accept_with_conditions",
          rationale: "Risk is moderate and every flag can be resolved by a condition.",
          decided_by: personId(DANIEL),
          decided_at: AT.accepted,
        },
        conditions: conditions(THORNBURY_CONDITIONS, SAMUEL),
        version: 15,
      };
    case "declined":
      return {
        ...base,
        status: "declined",
        decision: {
          option: "decline",
          rationale:
            "We can't confirm the executor's authority until the letters of office issue.",
          decided_by: personId(DANIEL),
          decided_at: AT.declined,
        },
        version: 15,
      };
  }
}

/** f: Meridian's FY2026 continuance, awaiting Margaret Okonkwo. */
export function meridianRecord(): AcceptanceRecordOut {
  const e = meridianEngagement().record;
  return {
    id: stableId("acceptance-record:meridian-fy2026"),
    engagement_id: e.id,
    client_id: e.client_id,
    kind: "continuance",
    status: "awaiting_partner",
    template_version_id: stableId("acceptance-template:audit-engagements:v2"),
    template_name: "Audit engagements v2",
    prepared_by: personId(HANNAH),
    risk_rating: "low",
    sections: [
      section("profile", "Engagement profile", "complete", "Complete · HL"),
      section(
        "integrity",
        "Management integrity screening",
        "complete",
        "No matches · OFAC & adverse media",
      ),
      section("independence", "Independence", "complete", "Assessed in CLI-08 · tax preparation"),
      section("scope", "Scope & complexity", "complete", "No changes from FY2025"),
      section(
        "identification",
        "Client identification & conflicts",
        "complete",
        "No conflicts found",
      ),
      section("prior", "Prior-year history", "flag", "1 flag · IL DOR notice open"),
      section("fees", "Fees & collectability", "complete", "No unpaid fees"),
      section("competence", "Competence & capacity", "complete", "Manufacturing audits: MO, HL"),
      section("conclusion", "Conclusion", "pending", null),
    ],
    flags: [
      {
        id: stableId("acceptance-flag:meridian:prior-year"),
        title: "Prior-year history — one open item",
        severity: "low",
        body: "FY2025 audit released Apr 2026 · IL DOR notice of tax due IL-1120 $5,880 (response sent Sep 2)\nNAS: the firm prepares the 2025 Form 1120",
        sources: [
          ref("evidence_version", "meridian:fy2025-audit-report"),
          ref("evidence_version", "meridian:il-dor-notice"),
        ],
        authored_by: personId(HANNAH),
        authored_at: AT.meridianFlag,
      },
    ],
    decision: null,
    conditions: [],
    risk_partner_review: null,
    prior: {
      record_id: stableId("acceptance-record:meridian-fy2025"),
      engagement_id: stableId("engagement:meridian:fy2025"),
      option: "accept",
      decided_at: "2025-09-15T15:00:00Z",
      conditions: [],
    },
    sent_to_partner_at: AT.meridianSent,
    sent_to_partner_by: personId(HANNAH),
    version: 11,
    allowed_actions: [],
  };
}

/** g: Granite Peak's FY2027 continuance on Oct 1, Draft, with the responsiveness flag. */
export function graniteRecord(): AcceptanceRecordOut {
  const e = graniteEngagement().record;
  return {
    id: stableId("acceptance-record:granite-fy2027"),
    engagement_id: e.id,
    client_id: e.client_id,
    kind: "continuance",
    status: "draft",
    template_version_id: stableId("acceptance-template:audit-engagements:v2"),
    template_name: "Audit engagements v2",
    prepared_by: personId(HANNAH),
    risk_rating: "low",
    sections: [
      section("profile", "Engagement profile", "complete", "Complete · HL"),
      section(
        "integrity",
        "Management integrity screening",
        "complete",
        "No matches · OFAC & adverse media",
      ),
      section("independence", "Independence", "pending", "In progress · HL"),
      section("scope", "Scope & complexity", "pending", "Not started"),
      section(
        "identification",
        "Client identification & conflicts",
        "complete",
        "No conflicts found",
      ),
      section(
        "prior",
        "Prior-year history",
        "complete",
        "FY2026 audit in fieldwork · release Oct 27",
      ),
      section(
        "responsiveness",
        "Client responsiveness",
        "flag",
        "1 flag · on-time rate 48% (firm 63%)",
      ),
      {
        ...section(
          "fees",
          "Fees & collectability",
          "manual_check_open",
          "Manual check · estate not yet in CCH Axcess Practice",
        ),
        manual_check: feeCheck(AT.graniteCheckAsked, GRACE, HANNAH, null),
      },
      section("competence", "Competence & capacity", "complete", "Distribution audits: MO, HL"),
      section("conclusion", "Conclusion", "pending", "Questionnaire in progress"),
    ],
    flags: [
      {
        id: stableId("acceptance-flag:granite:responsiveness"),
        title: "Client responsiveness is below the firm rate",
        severity: "low",
        body: "Granite Peak completed 48% of requests by their due date this season, against 63% for the firm (Jan 1 – Sep 30, 2026). Three FY2026 audit requests are overdue. Late support puts the FY2027 timetable at risk.",
        sources: [
          ref("evidence_version", "insights:client-responsiveness:granite"),
          ref("request_item", "granite:fy2026-overdue"),
        ],
        authored_by: personId(HANNAH),
        authored_at: AT.graniteFlag,
      },
    ],
    decision: null,
    conditions: [],
    risk_partner_review: null,
    prior: {
      record_id: stableId("acceptance-record:granite-fy2026"),
      engagement_id: stableId("engagement:granite-peak:fy2026"),
      option: "accept",
      decided_at: "2025-10-02T15:00:00Z",
      conditions: [],
    },
    sent_to_partner_at: null,
    sent_to_partner_by: null,
    version: 6,
    allowed_actions: [],
  };
}

/** g's continuance note, as Margaret Okonkwo wrote it in the dock (revision R2). */
export const GRANITE_NOTE =
  "Agree PBC dates and a named contact with Luis Ferrante before the FY2027 letter.";
