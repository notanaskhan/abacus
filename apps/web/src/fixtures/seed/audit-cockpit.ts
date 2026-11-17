// A-01-T06: Northwind's AUD-02 cockpit projections in fixture mode (docs/screens/AUD-02.md;
// docs/contracts/audits-cockpit.md), typed with the generated client. Fixture scenarios register
// every rail row so the artboards keep parity (A-01 DV-1); the live rail carries only registered
// providers. Three rail grammars: `run` (a: Marcus Delaney's run #4127 at 9:41 AM), `idle` (b: no
// run, every phase "Not started") and `pills` (g: the audit-program grammar). Words and figures are
// the AUD-02 spec's, verbatim; the Source Documents sub-line is counted from the seed's requests.

import type {
  AuditBandOut,
  AuditCockpitOut,
  AuditSectionRowOut,
  AuditSectionStatus,
} from "@abacus/api-client";
import { stableId } from "./prng";

/** `failed` is the run grammar with the Internal Control step failed (AUD-02 e, 9:58 AM). */
export type CockpitGrammar = "run" | "idle" | "pills" | "failed";

interface CockpitIds {
  workItemId: string;
  engagementId: string;
  clientId: string;
}

type Built = Pick<AuditSectionRowOut, "key" | "title" | "route" | "link">;

const OVERVIEW: readonly (Built & { sub?: string })[] = [
  {
    key: "client",
    title: "Client",
    route: "CLI-02",
    link: "live",
    sub: "Northwind Robotics, Inc.",
  },
  {
    key: "methodology",
    title: "Methodology",
    route: "KNW-03",
    link: "planned",
    sub: "BH Audit Methodology · EBP v3",
  },
  {
    key: "standards_set",
    title: "Standards set",
    route: "KNW-04",
    link: "planned",
    sub: "GAAS nonissuer · AU-C 703",
  },
  { key: "source_documents", title: "Source Documents", route: "AUD-03", link: "planned" },
  { key: "team", title: "Team", route: "ENG-05", link: "planned", sub: "MO · TW · HL · MD · AC" },
  { key: "activity", title: "Activity", route: "AUD-29", link: "planned" },
];

// [key, title, route, run state, run sub-line, idle-pill state]
type Section = readonly [string, string, string, AuditSectionStatus, string, AuditSectionStatus];
const PLANNING: readonly Section[] = [
  [
    "trial_balance",
    "Trial Balance",
    "AUD-06",
    "draft_ready",
    "Complete · 9:26 AM",
    "ready_to_run",
  ],
  [
    "materiality",
    "Materiality",
    "AUD-07",
    "blocked_on_decision",
    "Blocked on a partner decision",
    "in_progress",
  ],
  ["risk_assessment", "Risk Assessment", "AUD-05", "running", "Running", "in_progress"],
  [
    "general_audit_planning",
    "General Audit Planning",
    "AUD-04",
    "waiting_on_inputs",
    "Waiting on inputs",
    "in_progress",
  ],
  [
    "internal_control",
    "Internal Control",
    "AUD-09",
    "waiting_on_inputs",
    "Waiting on inputs",
    "in_progress",
  ],
  [
    "service_organizations",
    "Service Organizations & SOC 1",
    "AUD-10",
    "queued",
    "Queued",
    "not_started",
  ],
];
const FIELDWORK: readonly Section[] = [
  [
    "sample_selection",
    "Sample Selection",
    "AUD-11",
    "waiting_on_inputs",
    "Waiting on inputs",
    "in_progress",
  ],
  ["testing", "Testing", "AUD-12", "not_started", "Not started", "not_started"],
];

const MARGARET = stableId("user:margaret-okonkwo");
/** "Begin…" is the run engine's (P-10); the fixture grants it as AUD-02 a draws it. */
const BEGIN = "engagement_run.start";

function sectionRow(
  [key, title, route, runState, runLine, idleState]: Section,
  grammar: CockpitGrammar,
  workItemId: string,
): AuditSectionRowOut {
  const base = { key, title, route, link: "planned" as const, work_item_ref: workItemId };
  if (grammar === "pills") {
    return { ...base, grammar: "idle_pill", section_state: idleState, allowed_actions: [] };
  }
  if (grammar === "idle") {
    return {
      ...base,
      grammar: "sub_line",
      section_state: "not_started",
      sub_line: "Not started",
      allowed_actions: [],
    };
  }
  const failed = grammar === "failed" && key === "internal_control";
  return {
    ...base,
    grammar: "sub_line",
    section_state: failed ? "failed" : runState,
    sub_line: failed ? "Failed — see run" : runLine,
    ...(runState === "blocked_on_decision"
      ? { blocked_on_user_id: MARGARET, blocked_on_name: "Margaret Okonkwo" }
      : {}),
    allowed_actions: key === "testing" ? [BEGIN] : [],
  };
}

/** Northwind's cockpit: `received` of `total` from the seed's requests ("11 of 24 received"). */
export function northwindCockpit(
  ids: CockpitIds,
  grammar: CockpitGrammar,
  received: number,
  total: number,
): AuditCockpitOut {
  const overview: AuditBandOut = {
    key: "overview",
    rows: OVERVIEW.map((r) => ({
      key: r.key,
      title: r.title,
      route: r.route,
      link: r.link,
      work_item_ref: ids.workItemId,
      grammar: "link",
      section_state: null,
      sub_line:
        r.key === "source_documents"
          ? `${String(received)} of ${String(total)} received`
          : (r.sub ?? null),
      allowed_actions: [],
    })),
  };
  return {
    work_item_id: ids.workItemId,
    engagement_id: ids.engagementId,
    audit_bar: {
      title: "PY2025 Employee Benefit Plan Audit",
      methodology_label: "BH Audit Methodology · EBP v3",
      run_started_at:
        grammar === "run" || grammar === "failed" ? "2026-09-14T14:24:00.000Z" : null, // 9:24 AM CT
      auto_mode: null, // no `engagement_run.auto_mode` before P-10-T39
    },
    overview: {
      client_id: ids.clientId,
      client_name: "Northwind Robotics, Inc.",
      name: "Northwind Robotics 401(k) Plan",
      period_label: "PY2025",
      phase: "planning",
    },
    bands: [
      overview,
      { key: "planning", rows: PLANNING.map((s) => sectionRow(s, grammar, ids.workItemId)) },
      { key: "fieldwork", rows: FIELDWORK.map((s) => sectionRow(s, grammar, ids.workItemId)) },
      { key: "completion", collapsed: true, rows: [] },
      { key: "reporting", collapsed: true, rows: [] },
    ],
    dock_tabs: ["agent", "viewer"],
    phase_mode: "derived", // Planning: Fieldwork follows G4 (A-04-T43, DEC-2078)
    read_only_reason: null,
    version: 1,
    allowed_actions: [],
  };
}

/** AUD-02 h (A-09-T32; AUD-02 revision h, DEC-5408): Harlow & Pike's group audit at Planning, the
 * Group band between Planning and Fieldwork with the revision's three rows. Every word and figure
 * is the revision's (§9.2: 5 entities, 50,760,000, materiality 240,000 decided 3:40 PM, Pruett &
 * Lang LLP). */
export function harlowCockpit(ids: CockpitIds): AuditCockpitOut {
  const wid = ids.workItemId;
  const row = (
    key: string,
    title: string,
    route: string,
    state: NonNullable<AuditSectionRowOut["section_state"]>,
    sub: string,
  ): AuditSectionRowOut => ({
    key,
    title,
    route,
    link: "live",
    work_item_ref: wid,
    grammar: "sub_line",
    section_state: state,
    sub_line: sub,
    allowed_actions: [],
  });
  return {
    work_item_id: wid,
    engagement_id: ids.engagementId,
    audit_bar: {
      title: "FY2026 Group Financial Statement Audit",
      methodology_label: "BH Audit Methodology · FS v5",
      run_started_at: null,
      auto_mode: null,
    },
    overview: {
      client_id: ids.clientId,
      client_name: "Harlow & Pike Holdings, Inc.",
      name: "Harlow & Pike Holdings, Inc.",
      period_label: "FYE 12/31/2026 · group audit",
      phase: "planning",
    },
    bands: [
      { key: "overview", rows: [] },
      {
        key: "planning",
        rows: [
          row(
            "trial_balance",
            "Trial Balance",
            "AUD-31",
            "signed_off",
            "Mapped 244 of 244 · confirmed CD",
          ),
        ],
      },
      {
        key: "group",
        rows: [
          row("group_structure", "Structure", "AUD-32", "signed_off", "5 entities · finalized"),
          row(
            "group_scoping",
            "Scoping",
            "AUD-34",
            "signed_off",
            "Group materiality 240,000 · decided 3:40 PM",
          ),
          row(
            "component_auditors",
            "Component auditors",
            "AUD-35",
            "in_progress",
            "Pruett & Lang LLP · questionnaire received Sep 10",
          ),
        ],
      },
      { key: "fieldwork", rows: [] },
      { key: "completion", collapsed: true, rows: [] },
      { key: "reporting", collapsed: true, rows: [] },
    ],
    dock_tabs: ["agent", "viewer"],
    phase_mode: "derived",
    read_only_reason: null,
    version: 1,
    allowed_actions: [],
  };
}
