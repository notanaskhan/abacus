// A-07-T11: AUD-18 to AUD-25's fixture data on the Northwind PY2025 timeline (Oct 2 to Dec 3, 2026 and
// Jan 15, 2027), with the Granite Peak (Oct 26-27) and Lakeshore (Nov 10) variants. Typed by the stub's
// schemas, so `tsc` fails when a field an artboard draws has no server source. Figures from the handoff
// and A-07's goldens: 6 of 10, 12 of 17, 8 of 9, seal 7c41…a9e2, documentation date Dec 8, 2026. All
// names are fictional. Dev and test only.

import type {
  AuditArchiveStateOut,
  AuditCompletionOut,
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
    item_key: `eqr_${i + 1}`,
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
    rows: [{ key: "Overall", value: "252,200.00" }],
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
    rows: [{ key: "Uncorrected", value: "15,060.00" }],
    snapshot_sha256: HASH,
    source_kind: "conclusion",
    source_ref: "sum_conclusion",
    title: "Summary of misstatements",
  },
];

export function aud18(state: "a" | "b" | "b2" | "c" | "d" | "e"): EqrReviewOut {
  const done = state === "c" || state === "d" ? 10 : 6;
  const concurred = state === "d";
  return {
    work_item_id: COMPLETION_WORK_ITEM,
    required: true,
    eqr_name: "Thomas Whitcombe",
    status: concurred ? "concurred" : "in_progress",
    checklist: checklist(done),
    checklist_done: done,
    checklist_total: 10,
    digest_cards: DIGEST,
    notes:
      state === "c" || state === "d"
        ? []
        : [
            { id: stableId("eqr-note:1"), ref: "EQR-1", status: "responded", assignee_name: "Hannah Leclerc" },
            { id: stableId("eqr-note:2"), ref: "EQR-2", status: "open", assignee_name: "Hannah Leclerc" },
          ],
    concurrence: null,
    blockers: state === "a" || state === "b" || state === "b2" ? ["checklist_open:4", "eqr_notes_open:2"] : [],
    viewer_is_eqr: state !== "e",
    allowed_actions:
      state === "e" || concurred ? [] : ["eqr.mark_reviewed", "eqr.checklist_update"],
    version: 1,
  } as EqrReviewOut;
}

export function aud19(state: "a" | "a2" | "b" | "c" | "d" | "e" | "f"): AuditCompletionOut {
  const clear = state === "f";
  const granite = state === "e";
  return {
    work_item_id: COMPLETION_WORK_ITEM,
    items: [],
    complete: clear ? 17 : granite ? 14 : 12,
    not_applicable: 1,
    open: clear ? 0 : granite ? 3 : 5,
    total: 17,
    blockers: clear
      ? []
      : granite
        ? ["rep_letter", "bring_down", "governance_260"]
        : ["rep_letter", "fs_approval", "bring_down", "independence", "governance_260"],
    allowed_actions: ["completion.update"],
    version: 3,
  };
}

export function aud21(
  state: "a" | "a2" | "b" | "c" | "d" | "e" | "f",
): RepresentationLetterOut {
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

export function aud22(
  state: "a" | "a2" | "a3" | "b" | "c" | "d" | "e",
): GovernanceListOut {
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
  return { gate: g, met, required: true, value, blockers: met ? [] : ["envelope:out_for_signature"] };
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
