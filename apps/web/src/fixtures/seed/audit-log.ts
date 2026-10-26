// G-02-T04: ADM-07 audit-log fixtures (docs/contracts/audit-log.md), verbatim from the ADM-07
// handoff spec (ROWS 1–14, DETAIL DRAWER, STATES a–g) and G-02 §5.4. Brightwater Hale, synthetic;
// the clock is E0, Mon Sep 14, 2026, 9:24 AM CT. Codes and facts only: the SPA composes each
// title ("Report prepared by Hannah Leclerc via Agent") from `action` and the actor's facts.
//
// Not in the handoff, so not invented: the split of the 18,406 events between people and the
// system (`counts` carries `all`, `via_agent` and `policy` only), the export's row count, and the
// content hash's middle digits (the drawer shows "9f3c…a71e"; the filler between is the
// placeholder `0`s, as compliance.ts does for an unbuilt manifest). Rows whose producers are not
// built on staging (closes, tax returns, Workbench, inbox, envelopes) are fixture-only (G-02 §5.4).
import type {
  AuditActorOut,
  AuditEventDetail,
  AuditEventPageOut,
  AuditEventRow,
  AuditExport,
  AuditPersonOut,
  AuditValuesOut,
} from "@abacus/api-client";
import { officeIdOf } from "./firm-people";
import { stableId } from "./prng";

/** E0 in UTC: Mon Sep 14, 2026, 9:24 AM CDT. */
export const AUDIT_E0 = "2026-09-14T14:24:00Z";
/** ADM-07a "18,406 events · immutable" and b "4 of 1,962". */
export const AUDIT_TOTAL = 18_406;
export const VIA_AGENT_TOTAL = 1_962;
export const EMPTY_SEARCH = "pell street iii";

type Office = "Chicago" | "Denver" | "New York";
const person = (name: string, level: string, office: Office): AuditPersonOut => ({
  user_id: stableId(`user:${name.toLowerCase().replace(/[^a-z]+/g, "-")}`),
  display_name: name,
  level,
  office_id: officeIdOf(office),
});
export const PEOPLE = {
  marcus: person("Marcus Delaney", "senior", "Chicago"),
  hannah: person("Hannah Leclerc", "manager", "Chicago"),
  grace: person("Grace Holloway", "admin", "Chicago"),
  margaret: person("Margaret Okonkwo", "partner", "Chicago"),
  raj: person("Raj Malhotra", "senior", "Denver"),
  daniel: person("Daniel Reyes", "partner", "New York"),
  samuel: person("Samuel Ito", "manager", "New York"),
  neil: person("Neil Ashcroft", "partner", "Chicago"),
  olivia: person("Olivia Brandt", "senior", "Denver"),
  priya: person("Priya Raman", "partner", "Denver"),
  felix: person("Felix Andersen", "admin", "Chicago"),
} as const;

const asPerson = (p: AuditPersonOut): AuditActorOut => ({ kind: "person", person: p });
const viaAgent = (p: AuditPersonOut, agentId: string): AuditActorOut => ({
  kind: "via_agent",
  on_behalf_of: p,
  agent_id: agentId,
});
const SYSTEM: AuditActorOut = { kind: "system" };

/** Sep 14 or Sep 11, h:mm CDT, as UTC. */
function at(day: 11 | 14, hh: number, mm: number, ss = 0): string {
  const d = new Date(Date.UTC(2026, 8, day, hh + 5, mm, ss));
  return d.toISOString();
}
const target = (type: string, label: string, extra: Partial<AuditEventRow["target"]> = {}) => ({
  type,
  id: stableId(`audit-target:${type}:${label}`),
  label,
  ...extra,
});
const ASHFORD = stableId("client:ashford-manufacturing-co");
const runOf = (name: string) => stableId(`run:${name}`);

// ROWS 1–14, newest first. `seq` is an identifier: the newest is the log's 18,406th event.
const BASE: readonly Omit<AuditEventRow, "seq">[] = [
  {
    effective_at: at(14, 9, 24),
    action: "engagement_run.started",
    category: "run",
    mark: "pl",
    actor: asPerson(PEOPLE.marcus),
    target: target("engagement", "Northwind Robotics 401(k) Plan · PY2025 EBP Audit"),
    detail_facts: { plan_approval: "yes_run_it", auto_mode: false },
    ip: "198.51.100.24",
    run_id: runOf("northwind-ebp-run"),
    link_kind: "run",
  },
  {
    effective_at: at(14, 9, 21),
    action: "workbench_session.started",
    category: "run",
    mark: "pl",
    actor: asPerson(PEOPLE.hannah),
    target: target("workbench_session", "Workbench"),
    detail_facts: { topic: "TY2025 season progress by office" },
    ip: "198.51.100.31",
  },
  {
    effective_at: at(14, 9, 20),
    action: "wall.created",
    category: "decision",
    mark: "ok",
    actor: asPerson(PEOPLE.grace),
    target: target("wall", "Firm settings · Walls", { client_id: ASHFORD }),
    detail_facts: {
      walled_person: "Lena Park",
      client: "Ashford Manufacturing Co.",
      approved_by: "Margaret Okonkwo",
    },
    ip: "198.51.100.12",
  },
  {
    effective_at: at(14, 9, 18),
    action: "entry_batch.approved",
    category: "decision",
    mark: "ok",
    actor: asPerson(PEOPLE.raj),
    target: target("close", "Copperleaf Coffee Roasters, Inc. · Close 2026-08", {
      client_id: stableId("client:copperleaf-coffee-roasters-inc"),
    }),
    detail_facts: {
      policy: "BH AJE thresholds v2",
      within_threshold: 4,
      entry_1: "Payroll accrual",
      amount_1: "11860.00",
      entry_2: "Prepaid insurance",
      amount_2: "700.00",
      entry_3: "Depreciation",
      amount_3: "2140.00",
      entry_4: "Deferred revenue",
      amount_4: "5320.00",
      total: "20020.00",
    },
    ip: "198.51.100.57",
  },
  {
    effective_at: at(14, 9, 12),
    action: "inbox_email.received",
    category: "communication",
    mark: "pl",
    actor: SYSTEM,
    target: target("inbox_item", "Inbox · docs@brightwaterhale.com"),
    detail_facts: { from_name: "Claire Feld", attachments: 2, filed: false },
  },
  {
    effective_at: at(14, 9, 0),
    action: "agent_run.report_prepared",
    category: "run",
    mark: "pl",
    actor: viaAgent(PEOPLE.hannah, "workbench.season_progress_reporter"),
    target: target("agent_run", "Workbench · Agent run"),
    detail_facts: {
      agent: "Season Progress Reporter",
      schedule: "Mondays 9:00 AM CT",
      duration_s: 161,
      artifacts: 1,
    },
    run_id: runOf("season-progress-reporter"),
    link_kind: "run",
  },
  {
    effective_at: at(14, 8, 40),
    action: "envelope.sent",
    category: "communication",
    mark: "pl",
    actor: asPerson(PEOPLE.daniel),
    target: target("envelope", "Signatures · E13"),
    detail_facts: {
      document: "Engagement letter",
      title: "Ridgeline cost segregation & §754 analysis",
      signers: "Owen Calder, Daniel Reyes",
    },
    ip: "198.51.100.40",
  },
  {
    effective_at: at(14, 8, 31),
    action: "pii.revealed",
    category: "access",
    mark: "pl",
    actor: asPerson(PEOPLE.samuel),
    target: target("client", "Jonah & Claire Feld", {
      client_id: stableId("client:jonah-claire-feld"),
    }),
    detail_facts: { masked: "•••-••-2208", reason: "match to IRS wage & income transcript" },
    ip: "198.51.100.44",
  },
  {
    effective_at: at(14, 8, 5),
    action: "agent_run.reminders_drafted",
    category: "run",
    mark: "pl",
    actor: viaAgent(PEOPLE.grace, "workbench.request_chaser"),
    target: target("agent_run", "Workbench · Agent run"),
    detail_facts: { agent: "Request Chaser", schedule: "daily", drafts: 12, sent: 0 },
    run_id: runOf("request-chaser"),
    link_kind: "run",
  },
  {
    effective_at: at(14, 7, 58),
    action: "session.started",
    category: "sign_in",
    mark: "pl",
    actor: asPerson(PEOPLE.neil),
    target: target("auth_session", "Firm sign-in"),
    detail_facts: { method: "sso", provider: "Microsoft", mfa: true },
    ip: "198.51.100.18",
  },
  {
    effective_at: at(11, 16, 2),
    action: "acceptance_prescreen.drafted",
    category: "run",
    mark: "pl",
    actor: viaAgent(PEOPLE.daniel, "engagements.acceptance_prescreen"),
    target: target("client", "Estate of Walter Thornbury", {
      client_id: stableId("client:estate-of-walter-thornbury"),
    }),
    detail_facts: { flags: 3, awaiting: "partner_decision", return_information_read: false },
    run_id: runOf("thornbury-prescreen"),
    link_kind: "run",
  },
  {
    effective_at: at(11, 14, 47),
    action: "tax_return.exported",
    category: "export",
    mark: "ok",
    actor: asPerson(PEOPLE.samuel),
    target: target("tax_return", "Harborview Dental Properties, LP · 2025 Form 1065"),
    detail_facts: { destination: "CCH Axcess Tax", return_ref: "2025P:Harborview:V3" },
    ip: "198.51.100.44",
  },
  {
    effective_at: at(11, 14, 31),
    action: "tax_return.approved",
    category: "decision",
    mark: "ok",
    actor: asPerson(PEOPLE.daniel),
    target: target("tax_return", "Harborview Dental Properties, LP · 2025 Form 1065"),
    detail_facts: { gate: "BH-TAX-02", open_review_items: 0 },
    ip: "198.51.100.40",
  },
  {
    effective_at: at(11, 11, 6),
    action: "tax_return.self_checked",
    category: "run",
    mark: "pl",
    actor: viaAgent(PEOPLE.olivia, "tax.draft_self_check"),
    target: target("tax_return", "Ridgeline Property Partners, LP · 2025 Form 1065"),
    detail_facts: { routing_check_only: true },
  },
];

export const ADM07_ROWS: readonly AuditEventRow[] = BASE.map((row, i) => ({
  ...row,
  seq: AUDIT_TOTAL - i,
}));
/** Row 4, the Copperleaf batch the drawer (c) opens. */
export const COPPERLEAF_SEQ = AUDIT_TOTAL - 3;

/** ADM-07 d (fixture-only, ADR-187; `seq` set by `feed`): row 4 replaced by the policy's acceptance and Priya Raman's
 * reversal of Depreciation at 9:22 AM (G-02 §5.4); the note reads "2 events". */
export const POLICY_ROWS: readonly AuditEventRow[] = [
  {
    seq: 0,
    effective_at: at(14, 9, 22),
    action: "proposed_entry.acceptance_reversed",
    category: "decision",
    mark: "no",
    actor: asPerson(PEOPLE.priya),
    target: ADM07_ROWS[3]?.target ?? target("close", "Copperleaf"),
    detail_facts: {
      entry: "Depreciation",
      amount: "2140.00",
      reason: "asset_additions_unconfirmed",
    },
  },
  {
    seq: 0,
    effective_at: at(14, 9, 18),
    action: "entry_batch.accepted",
    category: "decision",
    mark: "ok",
    actor: { kind: "policy", policy_ref: "BH AJE thresholds v2" },
    target: ADM07_ROWS[3]?.target ?? target("close", "Copperleaf"),
    detail_facts: {
      entry_1: "Payroll accrual",
      amount_1: "11860.00",
      limit_1: "payroll_accruals_15000",
      entry_2: "Prepaid insurance",
      amount_2: "700.00",
      entry_3: "Depreciation",
      amount_3: "2140.00",
      entry_4: "Deferred revenue",
      amount_4: "5320.00",
      limit_2_to_4: "each_10000",
      reversible: true,
    },
  },
];

export type AuditView = "default" | "policy";

/** The feed for a view: the default, or d's with the policy rows in row 4's place. */
export function feed(view: AuditView): AuditEventRow[] {
  if (view === "default") return [...ADM07_ROWS];
  // d is its own log: the same events with row 4 replaced, numbered newest first.
  const rows = ADM07_ROWS.filter((r) => r.seq !== COPPERLEAF_SEQ);
  return [...POLICY_ROWS, ...rows]
    .sort((a, b) => b.effective_at.localeCompare(a.effective_at))
    .map((r, i) => ({ ...r, seq: AUDIT_TOTAL + 1 - i }));
}

export function page(
  items: AuditEventRow[],
  total: number,
  view: AuditView,
  more: boolean,
): AuditEventPageOut {
  return {
    items,
    next_cursor: more ? "fixture-load-more" : null,
    total,
    total_capped: false,
    counts: { all: AUDIT_TOTAL, via_agent: VIA_AGENT_TOTAL, policy: view === "policy" ? 2 : 0 },
    facets: {},
  };
}

const WITHHELD: AuditValuesOut = {
  status: "withheld",
  reason: "need_to_know",
  rows: [],
  not_included: [],
};
const UNAVAILABLE: AuditValuesOut = { status: "unavailable", rows: [], not_included: [] };

/** ADM-07c's values for Margaret Okonkwo (DEC-60): the batch foots 20,020.00; 14,900.00 stays
 * out for Priya Raman. */
export const COPPERLEAF_VALUES: AuditValuesOut = {
  status: "resolved",
  rows: [
    ["Payroll accrual", "11860.00"],
    ["Prepaid insurance", "700.00"],
    ["Depreciation", "2140.00"],
    ["Deferred revenue (subscriptions)", "5320.00"],
  ].map(([item, amount]) => ({
    item_label: item ?? "",
    field: "status",
    amount: amount ?? null,
    before: "within_threshold",
    after: "approved",
    masked: false,
  })),
  not_included: [
    {
      item_label: "Accrued expenses",
      amount: "14900.00",
      reason_code: "review_required_other_accruals_over_10000",
      routed_to: PEOPLE.priya,
    },
  ],
};

/** The drawer: Margaret (`quality_partner`, in scope) reads values; anyone else (Felix
 * `security_admin`, Grace `firm_admin`) gets metadata and the withheld reason. */
export function detail(
  seq: number,
  persona: string | undefined,
  view: AuditView,
): AuditEventDetail | undefined {
  const row = feed(view).find((r) => r.seq === seq);
  if (row === undefined) return undefined;
  const readsValues = persona === "margaret-okonkwo";
  const copperleaf = seq === COPPERLEAF_SEQ && view === "default";
  const human = row.actor.kind === "person" || row.actor.kind === "support";
  return {
    ...row,
    occurred_at: copperleaf ? at(14, 9, 18, 42) : row.effective_at,
    authority: copperleaf
      ? {
          code: "within_threshold_batch",
          facts: { policy: "BH AJE thresholds v2", approval_limit: "senior" },
        }
      : null,
    device_label: human ? (copperleaf ? "Chrome · macOS" : null) : null,
    user_agent_family: human && copperleaf ? "Chrome" : null,
    session: copperleaf
      ? {
          session_id: stableId("session:raj-malhotra:e0"),
          auth_method: "sso",
          mfa_at: at(14, 9, 1),
        }
      : null,
    content_hash: copperleaf ? `9f3c${"0".repeat(56)}a71e` : "0".repeat(64),
    values: readsValues ? (copperleaf ? COPPERLEAF_VALUES : UNAVAILABLE) : WITHHELD,
    source: copperleaf
      ? {
          run_id: runOf("copperleaf-close-2026-08"),
          agent_id: "closes.entry_proposer",
          run_no: 2,
          started_at: at(14, 9, 6),
          initiator: PEOPLE.raj,
        }
      : null,
  };
}

/** ADM-07 e → g: Felix's Sep 8–14 export with before/after values, ready. */
export const EXPORT_READY: AuditExport = {
  id: stableId("audit-export:felix-andersen:2026-09-08"),
  status: "ready",
  from_date: "2026-09-08",
  to_date: "2026-09-14",
  filter: {},
  include_values: true,
  requested_by: PEOPLE.felix,
  requested_at: AUDIT_E0,
  file_name: "audit-log-2026-09-08-2026-09-14.csv",
  row_count: null,
  seq_from: null,
  seq_to: null,
  manifest_sha256: "0".repeat(64),
  expires_at: "2026-09-21T14:24:00Z",
};
