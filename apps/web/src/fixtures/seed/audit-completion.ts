// A-07-T11: AUD-18 to AUD-25's fixture data on the Northwind PY2025 timeline (Oct 2 to Dec 3, 2026 and
// Jan 15, 2027), with the Granite Peak (Oct 26-27) and Lakeshore (Nov 10) variants. Typed by the stub's
// schemas, so `tsc` fails when a field an artboard draws has no server source. Figures from the handoff
// and A-07's goldens: 6 of 10, 12 of 17, 8 of 9, seal 7c41…a9e2, documentation date Dec 8, 2026. All
// names are fictional. Dev and test only.

import type {
  AgentRunOut,
  AuditArchiveStateOut,
  AuditCompletionItemOut,
  AuditCompletionOut,
  GoingConcernOut,
  LegalLetterOut,
  SubsequentEventsOut,
  AuditReleaseOut,
  AuditReportOut,
  EqrChecklistItemOut,
  EqrDigestCardOut,
  EqrReviewOut,
  GateCardOut,
  GovernanceListOut,
  RepresentationLetterOut,
} from "@abacus/api-client";
import { stableId } from "./prng";

export const COMPLETION_WORK_ITEM = stableId("work-item:northwind:py2025:assurance");
const HASH = "b".repeat(64);
export const SEAL = `7c41${"0".repeat(56)}a9e2`;

const CHECKLIST_TITLES = [
  "Independence and objectivity",
  "Significant judgments",
  "Materiality",
  "Significant risks",
  "Findings and uncorrected misstatements",
  "Going concern",
  "Financial statements and disclosures",
  "Proposed report",
  "EQR review notes",
  "Documentation",
];

function checklist(done: number): EqrChecklistItemOut[] {
  return CHECKLIST_TITLES.map((title, i) => ({
    item_key: `eqr_${String(i + 1)}`,
    position: i + 1,
    status: i < done ? "done" : "todo",
    sub_line: null,
    title,
    updated_by_name: i < done ? "Thomas Whitcombe" : null,
    version: 1,
  }));
}

const DIGEST: EqrDigestCardOut[] = [
  {
    citation_ids: [],
    id: stableId("eqr-digest:materiality"),
    link_target: "/audits/$auditId/materiality",
    reviewed_at: null,
    reviewed_by_name: null,
    rows: [{ label: "Overall", value: "252,200.00" }],
    snapshot_sha256: HASH,
    source_kind: "decision",
    source_ref: "planning_materiality",
    title: "Planning materiality",
  },
  {
    citation_ids: [],
    id: stableId("eqr-digest:sum"),
    link_target: "/audits/$auditId/misstatements",
    reviewed_at: null,
    reviewed_by_name: null,
    rows: [{ label: "Uncorrected", value: "15,060.00" }],
    snapshot_sha256: HASH,
    source_kind: "conclusion",
    source_ref: "sum_conclusion",
    title: "Summary of misstatements",
  },
];

export function aud18(state: "a" | "b" | "b2" | "c" | "d" | "e"): EqrReviewOut {
  // The screen contract's letters (A-07-T17): a 6 of 10 · b, b2 ready · c concurred · d the Agent
  // tab over a · e not the EQR over a.
  const ready = state === "b" || state === "b2";
  const concurred = state === "c";
  const done = ready || concurred ? 10 : 6;
  return {
    work_item_id: COMPLETION_WORK_ITEM,
    required: true,
    eqr_name: "Thomas Whitcombe",
    status: concurred ? "concurred" : ready ? "ready_to_concur" : "in_progress",
    checklist: checklist(done),
    checklist_done: done,
    checklist_total: 10,
    digest_cards: DIGEST,
    notes:
      ready || concurred
        ? []
        : [
            {
              id: stableId("eqr-note:1"),
              ref: "EQR-1",
              status: "responded",
              assignee_name: "Hannah Leclerc",
            },
            {
              id: stableId("eqr-note:2"),
              ref: "EQR-2",
              status: "open",
              assignee_name: "Hannah Leclerc",
            },
          ],
    concurrence: concurred
      ? {
          concurred_by_name: "Thomas Whitcombe",
          concurred_at: "2026-10-05T16:40:00-05:00",
          concurrence_date: "2026-10-05",
          not_involved_attested: true,
        }
      : null,
    blockers: ready || concurred ? [] : ["checklist_open:4", "eqr_notes_open:2"],
    viewer_is_eqr: state !== "e",
    allowed_actions:
      state === "e" || concurred
        ? []
        : ready
          ? ["eqr.mark_reviewed", "eqr.checklist_update", "eqr.concur"]
          : ["eqr.mark_reviewed", "eqr.checklist_update"],
    version: 1,
  };
}

// AUD-19 (A-07-T25): the 18 items of the Northwind completion checklist, verbatim from the handoff.
// Titles and evidence are the firm template's and the projector's words (database content); the
// fixture carries them as the read would.
type Aud19State = "a" | "a2" | "b" | "c" | "d" | "e" | "f";
type ItemStatus = AuditCompletionItemOut["status"];
const AUD19_ITEMS: readonly [string, string, string, ItemStatus, string | null][] = [
  ["procedures", "Planned procedures complete or explained", "25 of 26 workpapers prepared (only the Completion Checklist, in progress)", "done", "AUD-17"],
  ["review_notes", "Review notes closed", "14 of 14 cleared · Oct 5", "done", "AUD-17"],
  ["sign_offs", "Sign-offs current", "No workpaper changed after sign-off", "done", "AUD-17"],
  ["sum", "Misstatements evaluated", "SUM immaterial · MO Oct 2", "done", "AUD-16"],
  ["materiality", "Final materiality reassessed", "v3 · 16,861,000 × 1.5% = 252,900 · no change", "done", "AUD-07"],
  ["risk_standback", "Risk assessment stand-back", "No new risks · Oct 2", "done", "AUD-08"],
  ["consultations", "Consultations concluded", "C-03 · Sep 28", "done", "AUD-28"],
  ["independence", "Independence reconfirmed through report date", "Due Oct 9 · MO · TW · HL · MD · AC", "open", null],
  ["subsequent_events", "Subsequent events through report date", "Procedures to Oct 6 · bring-down Oct 9", "open", null],
  ["legal_letter", "Legal letters", "Not applicable · no plan litigation or claims (inquiry + committee minutes)", "not_applicable", null],
  ["going_concern", "Going concern", "No substantial doubt · MO Sep 30", "done", null],
  ["fs_tieout", "FS tie-out", "63 of 63 figures tie", "done", "AUD-20"],
  ["disclosure_checklist", "Disclosure checklist (ASC 962)", "142 of 142 answered", "done", "AUD-20"],
  ["form5500_tie", "Form 5500 read for consistency", "EBP-07 · differs only by the 48,600 receivable · Note 8", "done", "EBP-07"],
  ["mgmt_approval", "Management approval of the final FS", "Sent to Dana Kowalski Oct 6 (POR-09)", "open", "AUD-20"],
  ["rep_letter", "Representation letter signed, dated as of report date", "Out for signature · G7", "open", "AUD-21"],
  ["tcwg_260", "Governance communications", "AU-C 260 completion draft · AU-C 265/703 draft (due Dec 8)", "partial", "AUD-22"],
  ["eqr", "EQR concurrence", "Thomas Whitcombe · Oct 5 · G6", "done", "AUD-18"],
]; // prettier-ignore
const CLIENT = new Set(["mgmt_approval", "rep_letter"]);
const REPORT_DATE = new Set(["independence", "subsequent_events"]);
const GATES: Record<string, AuditCompletionItemOut["gate_tag"]> = { rep_letter: "G7", eqr: "G6" };

function aud19Items(state: Aud19State): AuditCompletionItemOut[] {
  const granite = state === "e";
  return AUD19_ITEMS.map(([key, title, evidence, base, link], i) => {
    let itemStatus: ItemStatus = base;
    if (state === "f" && base !== "not_applicable") itemStatus = "done";
    if (granite && (key === "independence" || key === "mgmt_approval")) itemStatus = "done";
    return {
      item_key: key,
      position: i + 1,
      title,
      status: itemStatus,
      derived: key !== "legal_letter",
      evidence_text: evidence,
      link_target: link,
      gate_tag: GATES[key] ?? null,
      depends_on_client: CLIENT.has(key),
      due_on: REPORT_DATE.has(key) ? "2026-10-09" : null,
      na_basis: base === "not_applicable" ? evidence : null,
      na_by_name: base === "not_applicable" ? "Hannah Leclerc" : null,
    };
  });
}

export function aud19(state: Aud19State): AuditCompletionOut {
  const items = aud19Items(state);
  const counted = items.filter((i) => i.status !== "not_applicable");
  return {
    work_item_id: COMPLETION_WORK_ITEM,
    items,
    complete: counted.filter((i) => i.status === "done").length,
    not_applicable: items.length - counted.length,
    open: counted.filter((i) => i.status !== "done").length,
    total: counted.length,
    blockers: counted.filter((i) => i.status !== "done").map((i) => i.item_key),
    allowed_actions: ["completion.update"],
    version: 3,
  };
}

export function aud19SubsequentEvents(): SubsequentEventsOut {
  const procedure = (
    key: string,
    title: string,
    through: string | null,
  ): SubsequentEventsOut["procedures"][number] => ({
    id: stableId(`se-procedure:${key}`),
    procedure_key: key,
    title,
    performed_through: through,
    performed_by_name: through === null ? null : "Hannah Leclerc",
    status: through === null ? "open" : "performed",
    run_id: null,
  });
  return {
    report_date: "2026-10-09",
    procedures: [
      procedure("inquiry", "Inquiry of the plan administrator — Dana Kowalski", "2026-10-06"),
      procedure("minutes", "Read benefits committee minutes through Sep 30, 2026", "2026-10-06"),
      procedure("trust_statements", "Read 2026 trust statements Jan–Aug for unusual activity", "2026-10-06"),
      procedure("amendments", "Plan amendments since Dec 31, 2025", "2026-10-06"),
      procedure("bring_down", "Bring-down inquiry on the report date", null),
    ], // prettier-ignore
    events: [
      {
        id: stableId("se-event:secure2"),
        description:
          "Plan amended Jul 15, 2026 for the SECURE 2.0 Roth catch-up requirement, effective Jan 1, 2026",
        recognition: "nonrecognized",
        fs_effect: "None",
        note_ref: "Note 11",
        citation_ids: [],
        recorded_by_name: "Hannah Leclerc",
        recorded_at: "2026-10-06T09:10:00-05:00",
      },
      {
        id: stableId("se-event:vfcp"),
        description:
          "Lost earnings of $64.38 on the late December 26, 2025 deferrals deposited Sep 30, 2026; VFCP Self-Correction Component notice filed Oct 1, 2026",
        recognition: "nonrecognized",
        fs_effect: "None",
        note_ref: "Note 9",
        citation_ids: [],
        recorded_by_name: "Hannah Leclerc",
        recorded_at: "2026-10-06T09:12:00-05:00",
      },
    ],
    bring_down: {
      scheduled_for: "2026-10-09T09:00:00-05:00",
      run_id: stableId("agent-run:4240"),
      status: "queued",
    },
    allowed_actions: ["subsequent_event.create", "subsequent_event.update"],
  };
}

export function aud19LegalLetters(): LegalLetterOut {
  return {
    status: "not_applicable",
    not_applicable: true,
    basis:
      "No litigation, claims or assessments against the plan. Basis: inquiry of Dana Kowalski (Oct 6) and benefits committee minutes through Sep 30. The rep letter carries the litigation representation.",
    request_item_id: null,
    allowed_actions: ["legal_letter.update", "legal_letter.request"],
    version: 2,
  };
}

export function aud19GoingConcern(state: Aud19State): GoingConcernOut {
  const granite = state === "e";
  return {
    state: "decided",
    decision_card_id: stableId(granite ? "card:granite:going-concern" : "card:going-concern"),
    conclusion: "no_substantial_doubt",
    decided_by_name: "Margaret Okonkwo",
    decided_at: granite ? "2026-10-26T09:40:00-05:00" : "2026-09-30T15:10:00-05:00",
    inputs: granite
      ? [
          { label: "DSCR covenant minimum", value: "1.25×, actual 1.32×." },
          { label: "Revolver", value: "$6,500,000 with Front Range Bank matures Mar 2028; term loan $3,200,000." },
        ]
      : [
          { label: "", value: "Northwind Robotics, Inc. does not intend to terminate or freeze the plan (committee minutes, Aug 2026)." },
          { label: "", value: "The match was funded every 2026 payroll." },
        ], // prettier-ignore
    reserved_to: "engagement_partner",
    allowed_actions: [],
  };
}

// AUD-19's dock (A-07-T25): run #4231 checked the 18 items at 9:12 AM; #4240, the bring-down, is
// queued for the report date at 9:00 AM (BringDownWorkflow).
export const RUN_4231_ID = stableId("agent-run:completion-readiness-4231");
export const RUN_4240_ID = stableId("agent-run:4240");

export function aud19Runs(): AgentRunOut[] {
  return [
    {
      id: RUN_4231_ID,
      agent: "completion_readiness",
      agent_label: "Completion readiness checker · run #4231",
      state: "succeeded",
      started_at: "2026-10-06T09:11:00-05:00",
      finished_at: "2026-10-06T09:12:00-05:00",
      duration_ms: 60000,
      initiator_name: "Hannah Leclerc",
      subject: null,
    },
    {
      id: RUN_4240_ID,
      agent: "subsequent_events_bring_down",
      agent_label: "Run subsequent-events bring-down · run #4240",
      state: "queued",
      started_at: "2026-10-09T09:00:00-05:00",
      finished_at: null,
      duration_ms: null,
      initiator_name: "Hannah Leclerc",
      subject: null,
    },
  ];
}

export function aud21(state: "a" | "a2" | "b" | "c" | "d" | "e" | "f"): RepresentationLetterOut {
  const statuses: Record<typeof state, RepresentationLetterOut["status"]> = {
    a: "draft",
    a2: "approved",
    b: "drafting",
    c: "awaiting_partner_approval",
    d: "sent",
    e: "signed",
    f: "date_mismatch",
  };
  const signed = state === "e";
  return {
    allowed_actions:
      state === "a2" ? ["rep_letter.send"] : state === "a" ? ["rep_letter.request_approval"] : [],
    current_version: null,
    dated_as_of: "2026-10-09",
    envelope_id: state === "d" || signed ? stableId("envelope:rep-letter") : null,
    g7_met: signed,
    paragraphs: [],
    report_date: "2026-10-09",
    representations: [],
    signed_on: signed ? "2026-10-09" : state === "f" ? "2026-10-07" : null,
    signers: [],
    status: statuses[state],
    version: 1,
    watermark: signed ? "none" : "draft",
  };
}

export function aud22(state: "a" | "a2" | "a3" | "b" | "c" | "d" | "e"): GovernanceListOut {
  return {
    allowed_actions:
      state === "a2"
        ? ["governance_comm.approve_send"]
        : state === "a3"
          ? ["governance_comm.request_approval"]
          : [],
    items: [],
    required_sent: state === "c" || state === "d" ? 2 : 1,
    required_total: 2,
  };
}

const REPORT_STATUS: Record<string, AuditReportOut["status"]> = {
  b: "approved",
  h: "released",
  i: "released",
  j: "reissued",
};

export function aud23(
  state: "a" | "b" | "c" | "d" | "e" | "f" | "g" | "h" | "i" | "j",
): AuditReportOut {
  return {
    allowed_actions: state === "a" ? ["report.draft", "sign_off.l4"] : [],
    choices: [],
    current_version: null,
    documents: [],
    eqr_required_not_concurred: state === "c",
    framework: "US GAAP · ASC 962",
    paragraphs: [],
    report_kind: "audit",
    status: REPORT_STATUS[state] ?? "draft",
    version: 1,
  };
}

function gate(g: GateCardOut["gate"], met: boolean, value: string | null): GateCardOut {
  return {
    gate: g,
    met,
    required: true,
    value,
    blockers: met ? [] : ["envelope:out_for_signature"],
  };
}

export function aud24(state: "a" | "b" | "c" | "d" | "e" | "f"): AuditReleaseOut {
  const open = state === "b";
  const released = state === "d" || state === "f";
  return {
    gates: [
      gate("G5", true, "Review complete"),
      gate("G6", true, "Concurred Oct 5, 2026"),
      gate("G7", !open, open ? null : "Signed Oct 9, 2026"),
    ],
    also_required: [
      { key: "fs_approved", met: true, value: "Oct 8, 2026" },
      { key: "bring_down", met: true, value: "#4240" },
      { key: "independence", met: true, value: "5 of 5" },
    ],
    gate_hash: HASH,
    can_release: !open && !released,
    viewer_can_release: state === "a" || state === "c",
    engagement_partner_name: "Margaret Okonkwo",
    released_at: released ? "2026-10-09T16:12:00-05:00" : null,
    released_by_name: released ? "Margaret Okonkwo" : null,
    documentation_completion_date: released ? "2026-12-08" : null,
    deliverable_ids: [],
    filings: [],
    allowed_actions: state === "a" || state === "c" ? ["report.release"] : [],
  };
}

const ARCHIVE_BASE: AuditArchiveStateOut = {
  status: "assembling",
  release_date: "2026-10-09",
  documentation_completion_date: "2026-12-08",
  days_left: 47,
  retention_until: "2033-10-09",
  on_hold: false,
  checklist: [],
  checklist_done: 8,
  checklist_total: 9,
  checklist_hash: HASH,
  binder: [],
  locked_at: null,
  locked_by_name: null,
  seal_sha256: null,
  additions: [],
  allowed_actions: ["archive.build_index"],
};

export function aud25(state: "a" | "b" | "b2" | "c" | "d" | "e"): AuditArchiveStateOut {
  const locked = state === "c" || state === "d";
  return {
    ...ARCHIVE_BASE,
    status: locked ? "locked" : "assembling",
    days_left: state === "e" ? 5 : state === "b" || state === "b2" ? 12 : locked ? 5 : 47,
    checklist_done: locked || state === "b" || state === "b2" ? 9 : 8,
    locked_at: locked ? "2026-12-03T16:18:00-06:00" : null,
    locked_by_name: locked ? "Margaret Okonkwo" : null,
    seal_sha256: locked ? SEAL : null,
    allowed_actions: locked ? [] : ["archive.build_index"],
  };
}
