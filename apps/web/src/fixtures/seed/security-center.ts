// G-02-T11: security-center v1 fixtures for ADM-06 (docs/contracts/security-center.md), built from
// the governance seed (governance.ts, G-02-T07; the golden governance_e0.json), the compliance
// kernel's fixtures (compliance.ts: INC-2026-005 and the export history), the ADM-07 seed's
// sign-in facts (audit-log.ts) and the ADM-06 handoff spec. Brightwater Hale, synthetic; E0 is
// Mon Sep 14, 2026, 9:24 AM CT.
//
// The interfaces below mirror the Pydantic models field for field
// (identity/security_center_contract.py, platform/security_center_contract.py,
// evidence/firm_export_schedule_contract.py). They stand in for the generated client's types
// until `make generate` runs at integration, when they are swapped for `@abacus/api-client`
// imports of the same names (TASK-1332).
//
// Not in the handoff, so not invented: who designated the break-glass account (the handoff names
// no person: it is "Break-glass account", its seat-holder label in ADM-06 i) and when each
// schedule approval was given (both are the audit log's, not the contract's); the closed
// incidents' decisions (DEC-419: closing INC-2026-003 and 004 waits for G-02-T18); the locked
// person behind "Unlocks automatically at 9:39 AM" (the unlock answer carries no name). The
// sessions drawer lists the two sessions the ADM-07 seed describes (Raj Malhotra's, signed in
// with MFA at 9:01 AM on Chrome · macOS, last seen at his 9:18 AM approval; Neil Ashcroft's SSO
// sign-in at 7:58 AM), nothing more. Retention (fieldset F) is Q-02's live contract
// (`GET /v1/retention/policies`); its record types are imported content with no seed codes, so
// it has no fixture here. Version numbers are 1 throughout.
import type { FirmExportOut, IncidentOut, SupportSessionOut } from "@abacus/api-client";
import { EXPORT_HISTORY, INC_2026_005 } from "./compliance";
import {
  FELIX,
  INC_2026_003,
  INC_2026_004,
  INC_2026_005_TIMELINE,
  LAST_SUPPORT_SESSION,
  MARGARET,
  type PersonRef,
  SIGN_IN_E0,
  SIGN_IN_JAN_11,
  WISP,
} from "./governance";
import { stableId } from "./prng";

/** E0 in UTC: Mon Sep 14, 2026, 9:24 AM CDT. */
export const SECURITY_E0 = "2026-09-14T14:24:00Z";
/** ADM-06 e: Sun Jan 11, 2026, 9:24 AM CST (the day before SSO was enforced). */
export const SECURITY_JAN_11 = "2026-01-11T15:24:00Z";

// --- Local mirrors of the contract's models (swapped for generated types after make generate) --

export type SecurityPersonOut = PersonRef;

export interface SsoExemptAccountOut {
  person: SecurityPersonOut;
  factor: "hardware_key";
  last_tested_at?: string | null;
}

export interface SignInPolicyOut {
  identity_provider?: string | null;
  sso_verified: boolean;
  require_sso: boolean;
  sso_enforced_at?: string | null;
  sso_enforced_by?: SecurityPersonOut | null;
  idp_mfa_attested_at?: string | null;
  idp_mfa_attested_by?: SecurityPersonOut | null;
  session_absolute_minutes: number;
  session_idle_minutes: number;
  platform_max_absolute_minutes?: number;
  platform_max_idle_minutes?: number;
  sso_exempt_account?: SsoExemptAccountOut | null;
  version: number;
}

export interface MfaSummaryOut {
  enforced: boolean;
  locked: boolean;
  enrolled: number;
  seats: number;
  idp_claim_counted?: boolean;
}

export interface PortalSignInFloorOut {
  passwordless_email_code: boolean;
  passwordless_locked: boolean;
  mfa_floor: boolean;
  mfa_floor_locked: boolean;
  failed_code_limit: number;
  lockout_minutes: number;
  lockout_locked: boolean;
  session_minutes: number;
  platform_max_session_minutes?: number;
  version: number;
}

export interface ResidencyOut {
  region: string;
  storage_primary_region?: string | null;
  storage_backup_region?: string | null;
  ai_inference: "us_only";
  logs_region: string;
  encryption_at_rest: "aes_256";
  encryption_in_transit: "tls_1_3";
  locked: boolean;
}

export interface SupportAccessOut {
  allow_support_requests: boolean;
  updated_at?: string | null;
  updated_by?: SecurityPersonOut | null;
  version: number;
}

export interface SecurityOverviewOut {
  sign_in: SignInPolicyOut;
  mfa: MfaSummaryOut;
  portal: PortalSignInFloorOut;
  residency: ResidencyOut;
  support: SupportAccessOut;
  actions?: string[];
}

export interface PostureOut {
  sso_enforced: boolean;
  mfa_enrolled: number;
  mfa_seats: number;
  residency_region: string;
  open_incidents: number;
  pub4557_open: number;
}

export interface SecuritySessionOut {
  id: string;
  person: SecurityPersonOut;
  started_at: string;
  last_seen_at: string;
  mfa_at?: string | null;
  auth_method?: "sso" | "email_code" | "passkey" | "totp" | null;
  ip?: string | null;
  device_label?: string | null;
  current?: boolean;
}

export interface SecuritySessionPageOut {
  items: SecuritySessionOut[];
  next_cursor?: string | null;
  total: number;
  total_capped?: boolean;
  counts?: Record<string, number>;
}

export interface SessionSignedOutOut {
  session_id: string;
  signed_out_at: string;
  signed_out_by: SecurityPersonOut;
}

export interface StaffLockOut {
  user_id: string;
  locked: boolean;
  unlocks_at?: string | null;
  cleared: boolean;
}

type DecisionKind = "close_not_reportable" | "start_notification";
type DeciderSeat = "partner" | "qualified_individual";

export interface IncidentDecisionOut {
  kind: DecisionKind;
  decided_by: SecurityPersonOut;
  seat: DeciderSeat;
  decided_at: string;
}

export interface IncidentPendingDecisionOut {
  kind: DecisionKind;
  first: IncidentDecisionOut;
  waiting_for: SecurityPersonOut;
  waiting_for_seat: DeciderSeat;
}

export interface SecurityIncidentOut {
  id: string;
  ref: string;
  title: string;
  event_kind: IncidentOut["event_kind"];
  discovered_at: string;
  consumers_affected?: number | null;
  unencrypted?: boolean | null;
  notification_event: boolean;
  ftc_notify_by: string;
  clock_day: number;
  clock_days: number;
  status: "investigating" | "closed";
  source: "firm" | "accrued";
  accrued_ref?: string | null;
  created_at: string;
  pending_decision?: IncidentPendingDecisionOut | null;
  decisions?: IncidentDecisionOut[];
  notification_started_at?: string | null;
}

export interface IncidentTimelineEntryOut {
  id: string;
  occurred_at: string;
  code: string;
  facts?: Record<string, string | number | boolean | null>;
  note?: string | null;
  source: "firm" | "accrued" | "system";
  author?: SecurityPersonOut | null;
  recorded_at: string;
}

export interface SecurityIncidentDetailOut extends SecurityIncidentOut {
  timeline?: IncidentTimelineEntryOut[];
  reminders_on?: string[];
}

export interface SecurityIncidentPageOut {
  items: SecurityIncidentOut[];
  next_cursor?: string | null;
  total: number;
  total_capped?: boolean;
  counts?: Record<string, number>;
}

type ExportContent =
  "clients" | "entities" | "files" | "workpapers" | "returns" | "closes" | "audit_log";

export interface ScheduleApprovalOut {
  seat: "security_admin" | "partner";
  approved_by: FirmExportOut["requested_by"];
}

export interface FirmExportScheduleOut {
  cadence: "monthly";
  day_of_month: 1;
  local_time: "02:00";
  time_zone: string;
  contents: ExportContent[];
  status: "pending_approval" | "active" | "paused";
  approvals?: ScheduleApprovalOut[];
  next_run_on?: string | null;
  version: number;
}

export interface WispOut {
  name: string;
  format: "irs_pub_5708";
  evidence_item_id?: string | null;
  approved_by?: SecurityPersonOut | null;
  approved_on?: string | null;
}

export interface SafeguardsControlOut {
  control_key: string;
  title: string;
  status: "evidenced" | "open";
  due_on?: string | null;
  scheduled_on?: string | null;
  evidence_item_id?: string | null;
}

export interface SafeguardsOut {
  qualified_individual?: SecurityPersonOut | null;
  wisp?: WispOut | null;
  annual_report_last_on?: string | null;
  annual_report_next_due_month?: string | null;
  controls_evidenced: number;
  controls_total: number;
  open_controls?: SafeguardsControlOut[];
  training_completed?: number | null;
  training_total?: number | null;
  ptin_attested?: number | null;
  ptin_total?: number | null;
  access_review?: {
    quarter: string;
    due_on: string;
    status: "not_started" | "in_progress" | "complete";
  } | null;
  updated_at?: string | null;
  updated_by?: SecurityPersonOut | null;
  version: number;
}

export interface WispPackOut {
  id: string;
  status: "preparing" | "ready";
  document_count?: number | null;
  file_name?: string | null;
  requested_by: SecurityPersonOut;
  requested_at: string;
  download_url?: string | null;
  expires_at?: string | null;
}

// --- The seed ------------------------------------------------------------------------------------

/** The actions each persona holds in this family (the matrix rows of G-02-T02). */
export const ACTIONS: Readonly<Record<string, readonly string[]>> = {
  "felix-andersen": [
    "security.read",
    "security.manage",
    "session.end",
    "staff.unlock",
    "support_session.read",
    "support_session.manage",
    "incident.read",
    "incident.manage",
    "incident.decide",
    "firm_export.read",
    "firm_export.request",
    "firm_export.approve",
    "firm_export.schedule",
  ],
  // quality_partner at partner level: reads, decides incidents, approves exports (ADM-06 f).
  "margaret-okonkwo": [
    "security.read",
    "incident.read",
    "incident.decide",
    "firm_export.read",
    "firm_export.approve",
  ],
};

/** Midnight CT on a date the handoff gives without a time (DEC-419's rule). */
const midnightCst = (day: string): string => `${day}T06:00:00Z`;
const midnightCdt = (day: string): string => `${day}T05:00:00Z`;

/** "1 · hardware key · last tested Aug 3, 2026". */
const BREAK_GLASS: SsoExemptAccountOut = {
  person: { user_id: stableId("user:break-glass-account"), display_name: "Break-glass account" },
  factor: "hardware_key",
  last_tested_at: midnightCdt("2026-08-03"),
};

/** Fieldset A at E0: Entra ID, Require SSO on since Jan 12, 2026 by Felix, 12 h and 30 min. */
export const SIGN_IN_POLICY_E0: SignInPolicyOut = {
  identity_provider: SIGN_IN_E0.provider,
  sso_verified: true,
  require_sso: SIGN_IN_E0.require_sso,
  sso_enforced_at: midnightCst(SIGN_IN_E0.sso_enforced_on ?? "2026-01-12"),
  sso_enforced_by: FELIX,
  idp_mfa_attested_at: null,
  idp_mfa_attested_by: null,
  session_absolute_minutes: 720,
  session_idle_minutes: 30,
  platform_max_absolute_minutes: 720,
  platform_max_idle_minutes: 30,
  sso_exempt_account: BREAK_GLASS,
  version: 1,
};

/** ADM-06 e: the day before enforcement. Felix enforced it the next day, so a verified admin
 * SSO sign-in existed. */
export const SIGN_IN_POLICY_JAN_11: SignInPolicyOut = {
  ...SIGN_IN_POLICY_E0,
  require_sso: SIGN_IN_JAN_11.require_sso,
  sso_enforced_at: null,
  sso_enforced_by: null,
};

export const MFA_E0: MfaSummaryOut = {
  enforced: true,
  locked: true,
  enrolled: SIGN_IN_E0.mfa_enrolled,
  seats: SIGN_IN_E0.seats,
  idp_claim_counted: false,
};
/** "41 of 46 enrolled" and "5 users without MFA." */
export const MFA_JAN_11: MfaSummaryOut = {
  ...MFA_E0,
  enrolled: SIGN_IN_JAN_11.mfa_enrolled,
  seats: SIGN_IN_JAN_11.seats,
};

/** Fieldset B with the T03 deviations: DF-17's MFA floor and DEC-35's "3 codes · 15 minutes". */
export const PORTAL_POLICY: PortalSignInFloorOut = {
  passwordless_email_code: true,
  passwordless_locked: true,
  mfa_floor: true,
  mfa_floor_locked: true,
  failed_code_limit: 3,
  lockout_minutes: 15,
  lockout_locked: true,
  session_minutes: 480,
  platform_max_session_minutes: 480,
  version: 1,
};

/** Fieldset E: United States; storage primary Ohio, backup Oregon; AI inference US only. */
export const RESIDENCY: ResidencyOut = {
  region: "us",
  storage_primary_region: "us-east-2",
  storage_backup_region: "us-west-2",
  ai_inference: "us_only",
  logs_region: "us",
  encryption_at_rest: "aes_256",
  encryption_in_transit: "tls_1_3",
  locked: true,
};

export const SUPPORT_ACCESS_ON: SupportAccessOut = {
  allow_support_requests: true,
  updated_at: null,
  updated_by: null,
  version: 1,
};

export type SecurityView = "e0" | "jan_11";

export function overview(view: SecurityView, persona: string | undefined): SecurityOverviewOut {
  const jan = view === "jan_11";
  return {
    sign_in: jan ? SIGN_IN_POLICY_JAN_11 : SIGN_IN_POLICY_E0,
    mfa: jan ? MFA_JAN_11 : MFA_E0,
    portal: PORTAL_POLICY,
    residency: RESIDENCY,
    support: SUPPORT_ACCESS_ON,
    actions: [...(ACTIONS[persona ?? "felix-andersen"] ?? [])],
  };
}

/** The Posture card at E0: SSO enforced, MFA 46/46, US residency, 1 open incident, 2 Pub 4557
 * items open. */
export const POSTURE_E0: PostureOut = {
  sso_enforced: true,
  mfa_enrolled: MFA_E0.enrolled,
  mfa_seats: MFA_E0.seats,
  residency_region: RESIDENCY.region,
  open_incidents: 1,
  pub4557_open: WISP.controls_total - WISP.controls_evidenced,
};

// --- Sessions and unlock (T03's new rows) ---------------------------------------------------------

const RAJ = { user_id: stableId("user:raj-malhotra"), display_name: "Raj Malhotra" };
const NEIL = { user_id: stableId("user:neil-ashcroft"), display_name: "Neil Ashcroft" };

export const SESSIONS: readonly SecuritySessionOut[] = [
  {
    id: stableId("session:raj-malhotra:e0"),
    person: RAJ,
    started_at: "2026-09-14T14:01:00Z",
    last_seen_at: "2026-09-14T14:18:00Z",
    mfa_at: "2026-09-14T14:01:00Z",
    auth_method: "sso",
    ip: "198.51.100.57",
    device_label: "Chrome · macOS",
    current: false,
  },
  {
    id: stableId("session:neil-ashcroft:e0"),
    person: NEIL,
    started_at: "2026-09-14T12:58:00Z",
    last_seen_at: "2026-09-14T12:58:00Z",
    mfa_at: "2026-09-14T12:58:00Z",
    auth_method: "sso",
    ip: "198.51.100.18",
    device_label: null,
    current: false,
  },
];

/** "Unlocks automatically at 9:39 AM" (DEC-35): the identity provider kept the lock. */
export function stillLocked(userId: string): StaffLockOut {
  return { user_id: userId, locked: true, unlocks_at: "2026-09-14T14:39:00Z", cleared: false };
}

// --- Incidents (fieldset C and drawer d) -------------------------------------------------------

function row(incident: IncidentOut, status: SecurityIncidentOut["status"]): SecurityIncidentOut {
  return {
    id: incident.id,
    ref: incident.ref,
    title: incident.title,
    event_kind: incident.event_kind,
    discovered_at: incident.discovered_at,
    consumers_affected: incident.consumers_affected ?? null,
    unencrypted: incident.unencrypted ?? null,
    notification_event: incident.notification_event,
    ftc_notify_by: incident.ftc_notify_by,
    clock_day: incident.clock_day,
    clock_days: incident.clock_days,
    status,
    source: incident.source,
    accrued_ref: incident.accrued_ref ?? null,
    created_at: incident.created_at,
    pending_decision: null,
    decisions: [],
    notification_started_at: null,
  };
}

export const INCIDENT_005: SecurityIncidentOut = row(INC_2026_005, "investigating");
export const INCIDENTS: readonly SecurityIncidentOut[] = [
  INCIDENT_005,
  row(INC_2026_004, "closed"),
  row(INC_2026_003, "closed"),
];

/** A timeline date without a time is midnight CDT. Only the QI appends entries
 * (`incident.manage` is `security_admin`'s), so each firm entry is Felix's. */
const atOf = (at: string): string => (at.length === 10 ? midnightCdt(at) : at);
export const INCIDENT_005_DETAIL: SecurityIncidentDetailOut = {
  ...INCIDENT_005,
  timeline: INC_2026_005_TIMELINE.map((entry, i) => ({
    id: stableId(`incident:INC-2026-005:timeline:${String(i + 1)}`),
    occurred_at: atOf(entry.at),
    code: entry.code,
    facts: entry.facts,
    note: null,
    source: "firm",
    author: FELIX,
    recorded_at: atOf(entry.at),
  })),
  // Days 20, 25 and 29 of the clock that starts on Sep 10.
  reminders_on: ["2026-09-30", "2026-10-05", "2026-10-09"],
};

/** AC-22: Felix (the QI) has closed it as not reportable and named Margaret; it waits for her. */
export function waitingForMargaret(kind: DecisionKind, at: string): SecurityIncidentOut {
  return {
    ...INCIDENT_005,
    pending_decision: {
      kind,
      first: { kind, decided_by: FELIX, seat: "qualified_individual", decided_at: at },
      waiting_for: MARGARET,
      waiting_for_seat: "partner",
    },
  };
}

export function incidentPage(items: readonly SecurityIncidentOut[]): SecurityIncidentPageOut {
  const open = items.filter((i) => i.status === "investigating").length;
  return {
    items: [...items],
    next_cursor: null,
    total: items.length,
    total_capped: false,
    counts: { open, closed: items.length - open },
  };
}

// --- Export schedule (the Data export card and its history tray) --------------------------------

/** "Monthly · 1st at 2:00 AM CT", approved by "Two people: Felix Andersen + Margaret Okonkwo",
 * next Oct 1, 2026. The history is Q-02's list (compliance.ts). */
export const SCHEDULE_E0: FirmExportScheduleOut = {
  cadence: "monthly",
  day_of_month: 1,
  local_time: "02:00",
  time_zone: "America/Chicago",
  contents: ["clients", "entities", "files", "workpapers", "returns", "closes", "audit_log"],
  status: "active",
  approvals: [
    { seat: "security_admin", approved_by: FELIX },
    { seat: "partner", approved_by: MARGARET },
  ],
  next_run_on: "2026-10-01",
  version: 1,
};
export const SCHEDULED_RUNS: readonly FirmExportOut[] = EXPORT_HISTORY;

// --- Safeguards (fieldset D, ADM-06 h) ---------------------------------------------------------

export const SAFEGUARDS_E0: SafeguardsOut = {
  qualified_individual: FELIX,
  wisp: {
    name: WISP.name,
    format: "irs_pub_5708",
    evidence_item_id: stableId("evidence:bh-wisp-v4"),
    approved_by: WISP.approved_by,
    approved_on: WISP.approved_on,
  },
  annual_report_last_on: "2025-12-10",
  annual_report_next_due_month: "2026-12",
  controls_evidenced: WISP.controls_evidenced,
  controls_total: WISP.controls_total,
  open_controls: [
    {
      control_key: "annual_penetration_test",
      title: "Annual penetration test",
      status: "open",
      due_on: null,
      scheduled_on: "2026-10-06",
      evidence_item_id: null,
    },
    {
      control_key: "incident_tabletop_exercise",
      title: "Incident tabletop exercise",
      status: "open",
      due_on: "2026-11-30",
      scheduled_on: null,
      evidence_item_id: null,
    },
  ],
  training_completed: 46,
  training_total: 46,
  ptin_attested: 21,
  ptin_total: 21,
  access_review: { quarter: "2026-Q3", due_on: "2026-09-30", status: "in_progress" },
  updated_at: null,
  updated_by: null,
  version: 1,
};

/** "WISP evidence pack prepared · 14 documents". */
export const WISP_PACK: WispPackOut = {
  id: stableId("wisp-pack:felix-andersen:2026-09-14"),
  status: "ready",
  document_count: 14,
  file_name: null,
  requested_by: FELIX,
  requested_at: SECURITY_E0,
  download_url: "https://exports.invalid/wisp-pack.zip",
  expires_at: null,
};

// --- Support sessions (SPEC-012's routes; the card and T03's support states) -----------------

/** Aug 17, 2026 · 10:12–11:40 AM · Jordan Pryce (Accrued Support) · integration settings only.
 * `state` picks the card's state: closed (the seed), requested ("Awaiting firm approval"),
 * active ("Granted until 11:40 AM") or revoked. "Declined" is stored from G-02-T14 (DEC-72) and
 * its fixture lands with it. */
export type SupportState = "closed" | "requested" | "active" | "revoked";
export function supportSession(state: SupportState): SupportSessionOut {
  const on = LAST_SUPPORT_SESSION.on;
  const start = `${on}T15:12:00Z`;
  const end = `${on}T16:40:00Z`;
  const status = state === "closed" ? "ended" : state;
  return {
    id: stableId(`support-session:${on}`),
    staff_id: stableId("staff:jordan-pryce"),
    staff_subject: "Jordan Pryce",
    reason: "Integration settings only",
    scope: "metadata",
    duration_minutes: 88,
    emergency: false,
    status,
    approved_by_kind: state === "requested" ? null : "firm_admin",
    starts_at: state === "requested" ? null : start,
    expires_at: state === "requested" ? null : end,
    // A revocation's time is not in the handoff.
    ended_at: state === "closed" ? end : null,
    acknowledged: false,
    created_at: start,
    requests: 1,
  };
}
