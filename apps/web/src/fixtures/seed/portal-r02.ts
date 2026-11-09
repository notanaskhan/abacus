// R-02-T13 (TASK-6313; R-02 §3 POR-08, POR-09, POR-15; DEC-3013): the Brightwater Hale portal slice
// for approvals, deliverables and the governance room, transcribed from the figures book
// (backend/tests/golden/scenario/brightwater_hale/portal_figures.json, R-02-T08) so fixture mode
// and the seeded tenant read one source. Every amount is the book's; the arithmetic is footed in
// portal-r02.foot.test.ts (35,300; 14,900; 22,250; 16,861,000; 468,008). Synthetic only.
//
// Personas: Dana Kowalski (Northwind's plan administrator: the management grant), Victoria Lam
// (Benefits Committee chair: a `tcwg` grant on the room), Ben Ashby (Copperleaf's owner, the close
// package) and Meera Shah (Ridgeline's partner, her K-1).
import type {
  ApprovalItemDetailOut,
  ApprovalItemOut,
  ApprovalsOut,
  GovernanceCommunicationsOut,
  GovernanceLetterOut,
  GovernanceRoomsOut,
} from "@abacus/api-client";
import { stableId } from "./prng";

export const R02_CLOCK = "2026-09-25T10:00:00-05:00"; // Sep 25: the client's entry decisions
export const PERSONAS = {
  dana: "dana-kowalski",
  victoria: "victoria-lam",
  ben: "ben-ashby",
  meera: "meera-shah",
} as const;

export const ID = {
  aje1: stableId("proposed-entry:northwind-aje-1"),
  rje1: stableId("proposed-entry:northwind-rje-1"),
  paje1: stableId("proposed-entry:northwind-paje-1"),
  paje2: stableId("proposed-entry:northwind-paje-2"),
  uncorrected: stableId("uncorrected:northwind-py2025"),
  draftV3: stableId("statement-version:northwind-fs-v3"),
  draftV4: stableId("statement-version:northwind-fs-v4"),
  copperleafPackage: stableId("close-package:copperleaf-2026-08"),
  room: stableId("governance-body:northwind-benefits-committee"),
  planningLetter: stableId("governance-communication:northwind-planning-260"),
} as const;

/** The two attest entries' lines (the book's receivable and accrued groups). */
export const RECEIVABLE_LINES = ["33540.00", "15060.00"] as const; // = 48,600.00
export const ACCRUED_LINES = ["6150.00", "2400.00", "4500.00"] as const; // = 13,050.00
/** Copperleaf's posted entries (fixture only: the portal never posts) and its accrued group. */
export const POSTED = ["11860", "700", "2140", "5320", "14900", "380"] as const; // = 35,300
export const ACCRUED_EXPENSES = ["12600", "1480", "820"] as const; // = 14,900
export const UNCORRECTED = { increase: "35300.00", decrease: "13050.00", net: "22250.00" };
/** POR-09's page 2 of draft v3: investments and receivables to net assets. */
export const PAGE_2 = {
  investments: ["14895000", "1605000"] as const, // = 16,500,000
  receivables: ["312400", "48600"] as const, // = 361,000
  netAssets: "16861000",
};
/** Meera's 2025 Schedule K-1 (Form 1065) from Ridgeline Property Partners, LP. */
export const K1_BOXES = { "2": "468008", "5": "6992", "18A": "2356", "19A": "228000" } as const;

function waiting(
  kind: ApprovalItemOut["kind"],
  id: string,
  title: string,
  amount: string | null,
  actions: ApprovalItemOut["allowed_actions"],
): ApprovalItemOut {
  return {
    kind,
    id,
    title,
    state: "waiting",
    amount,
    decided_by: null,
    decided_at: null,
    reason_code: null,
    question_sent_at: null,
    allowed_actions: actions,
  };
}

const SEP_25 = "2026-09-25T15:02:00Z";

/** POR-08 for Dana on Sep 25, before her decisions (a) and after them (e). */
const AJE_1 = waiting("proposed_entry", ID.aje1, "AJE-1 · Contributions receivable", "48600.00", [
  "accept",
  "decline",
  "ask",
]);
const RJE_1 = waiting("proposed_entry", ID.rje1, "RJE-1 · Accrued expenses", "13050.00", [
  "accept",
  "decline",
  "ask",
]);
const PAJE_1 = waiting(
  "proposed_entry",
  ID.paje1,
  "PAJE-1 · Prior-period receivable",
  "33540.00",
  ["accept", "decline", "ask"],
);
const PAJE_2 = waiting(
  "proposed_entry",
  ID.paje2,
  "PAJE-2 · Prior-period receivable",
  "15060.00",
  ["accept", "decline", "ask"],
);

export const APPROVALS_BEFORE: ApprovalsOut = {
  items: [AJE_1, RJE_1, PAJE_1, PAJE_2],
  counts: { waiting: 4, posted: 0, approved: 0, declined: 0 },
  contexts: [],
};

export const APPROVALS_AFTER: ApprovalsOut = {
  items: [
    {
      ...AJE_1,
      state: "accepted",
      decided_by: "Dana Kowalski (client)",
      decided_at: SEP_25,
      allowed_actions: ["ask"],
    },
    {
      ...RJE_1,
      state: "accepted",
      decided_by: "Dana Kowalski (client)",
      decided_at: SEP_25,
      allowed_actions: ["ask"],
    },
    {
      ...PAJE_1,
      state: "declined",
      decided_by: "Dana Kowalski (client)",
      decided_at: SEP_25,
      reason_code: "other",
      allowed_actions: ["ask"],
    },
    {
      ...PAJE_2,
      state: "declined",
      decided_by: "Dana Kowalski (client)",
      decided_at: SEP_25,
      reason_code: "other",
      allowed_actions: ["ask"],
    },
    waiting(
      "uncorrected_misstatements",
      ID.uncorrected,
      "Uncorrected misstatements",
      UNCORRECTED.net,
      ["acknowledge", "ask"],
    ),
  ],
  counts: { waiting: 1, posted: 0, approved: 2, declined: 2 },
  contexts: [],
};

export const AJE1_DETAIL: ApprovalItemDetailOut = {
  ...AJE_1,
  seen_hash: "fixture-aje-1-v1",
  lines: [
    { account: "1210 Contributions receivable", debit: "48600.00", credit: null },
    { account: "4100 Employer contributions", debit: null, credit: "33540.00" },
    { account: "4110 Participant contributions", debit: null, credit: "15060.00" },
  ],
  parts: [],
  support: [],
  legend: null,
  highlights: null,
  reason: null,
};

/** POR-15 for Victoria: the Benefits Committee room and its planning letter (acknowledged). */
export const ROOMS: GovernanceRoomsOut = {
  items: [
    {
      id: ID.room,
      body_name: "Benefits Committee",
      subject: "Northwind Robotics 401(k) Plan",
      member_role: "chair",
      questions_for_you: 2,
    },
  ],
};

const COMMITTEE: GovernanceCommunicationsOut["committee"] = [
  { name: "Victoria Lam", member_role: "chair", acknowledged_on: "2026-09-21" },
  { name: "Robert Haines", member_role: "member", acknowledged_on: "2026-09-21" },
  { name: "Dana Kowalski", member_role: "member", acknowledged_on: "2026-09-21" },
];

export const ROOM_LETTERS: GovernanceCommunicationsOut = {
  items: [
    {
      id: ID.planningLetter,
      title: "Planning communication (AU-C 260)",
      status: "acknowledged",
      sent_on: "2026-09-17",
      due_on: null,
      acknowledged_on: "2026-09-21",
    },
    {
      id: null,
      title: "Communication at completion (AU-C 260)",
      status: "not_yet",
      sent_on: null,
      due_on: null,
      acknowledged_on: null,
    },
  ],
  committee: COMMITTEE,
};

export const PLANNING_LETTER: GovernanceLetterOut = {
  id: ID.planningLetter,
  title: "Planning communication (AU-C 260)",
  dated_on: "2026-09-17",
  signed_by: "Margaret Okonkwo",
  sections: [],
  status: "acknowledged",
  seen_hash: "fixture-planning-260-v1",
  committee: COMMITTEE,
  allowed_actions: ["ask", "download"],
};
