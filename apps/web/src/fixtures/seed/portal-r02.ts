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
  DeliverableOut,
  DeliverableRowOut,
  DeliverablesOut,
  DeliverableVersionOut,
  PageCommentsOut,
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
  // The book's AJE-1 lines (AUD-16's accounts; R-02-T13, DEC-4807): the seed writes the same.
  lines: [
    {
      account: "1250 Employer & participant contributions receivable",
      debit: "48600.00",
      credit: null,
    },
    { account: "4100 Participant contributions", debit: null, credit: "33540.00" },
    { account: "4200 Employer contributions", debit: null, credit: "15060.00" },
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

// --- POR-09 Deliverables (R-02-T17): the rail and the viewer by artboard, from the handoff's
// figures. Titles, page counts and dates are the book's (pack 7 and §9.4).

export const DELIVERABLE_ID = {
  fs: stableId("deliverable:northwind-fs-py2025"),
  rep: stableId("deliverable:northwind-rep-letter"),
  engagement: stableId("deliverable:northwind-engagement-letter"),
  report: stableId("deliverable:northwind-auditor-report"),
  copperleaf: stableId("deliverable:copperleaf-2026-08-statements"),
} as const;

export type Por09State = "a" | "a2" | "b" | "c" | "d" | "e" | "f";

function row(
  id: string,
  title: string,
  status: DeliverableRowOut["status"],
  over: Partial<DeliverableRowOut> = {},
): DeliverableRowOut {
  return { id, kind: "other", title, status, restricted_use: false, ...over };
}

const FS_TITLE = "Financial statements and supplemental schedules";

/** `GET /v1/portal/deliverables` by artboard. */
export function deliverables(state: Por09State): DeliverablesOut {
  if (state === "f") return { bands: [], coming_next: [], k1s: [] };
  if (state === "d") {
    return {
      bands: [
        {
          key: "tax-return-2025",
          label: "2025 Tax Return",
          rows: [
            row(stableId("deliverable:meera-return-2025"), "2025 Tax Return", "not_ready_yet", {
              kind: "return_copy",
            }),
          ],
        },
      ],
      coming_next: [],
      k1s: [
        {
          package_id: stableId("portal-k1:meera-shah"),
          title: "Ridgeline Property Partners, LP — 2025 Schedule K-1 (Form 1065)",
          released_on: "2026-09-15",
        },
      ],
    };
  }
  if (state === "e") {
    return {
      bands: [
        {
          key: "copperleaf-close-2026-08",
          label: "August 2026 Close",
          rows: [
            row(
              DELIVERABLE_ID.copperleaf,
              "August 2026 financial statements",
              "waiting_for_approval",
              {
                kind: "close_package",
                released_on: "2026-09-14",
              },
            ),
          ],
        },
      ],
      coming_next: [],
      k1s: [],
    };
  }
  const final = state === "c";
  return {
    bands: [
      {
        key: "northwind-py2025",
        label: "PY2025 plan audit",
        rows: final
          ? [
              row(DELIVERABLE_ID.report, "Independent auditor's report.pdf", "final", {
                kind: "auditor_report",
                page_count: 3,
              }),
              row(DELIVERABLE_ID.fs, `${FS_TITLE}.pdf`, "final", {
                kind: "fs_final",
                page_count: 14,
              }),
            ]
          : [
              row(
                DELIVERABLE_ID.fs,
                FS_TITLE,
                state === "b" ? "approved_by_you" : "for_your_review",
                { kind: "fs_draft", latest_version: state === "a" ? 3 : 4, page_count: 14 },
              ),
              row(DELIVERABLE_ID.rep, "Representation letter", "in_sign"),
              row(DELIVERABLE_ID.engagement, "Engagement letter", "signed", {
                kind: "signed_copy",
              }),
            ],
      },
    ],
    coming_next: final
      ? []
      : [
          { label: "Independent auditor's report", expected: "At release · expected Oct 9" },
          {
            label: "Form 5500",
            expected: "Filed by you with Summit Plan Administrators · due Oct 15 (extended)",
          },
        ],
    k1s: [],
  };
}

const HASH_V3 = "3e0a9c55b1d74f62a8e3f019c7d2b4a6e5f81c3d09b7a2e4f6c8d0b1a3e5f7c9";
const HASH_V4 = "7c41d8a2e9f03b56c1d7e4a8b2f60c9d3e5a7b1c4d8f2a6e0b3c5d7e9f1a2b4c";

function version(
  no: number,
  draft: boolean,
  pages: number,
  actions: DeliverableVersionOut["allowed_actions"],
  hash: string,
  publishedAt: string,
): DeliverableVersionOut {
  return {
    version_no: no,
    is_draft: draft,
    page_count: pages,
    page_comments: draft,
    published_at: publishedAt,
    seen_hash: hash,
    withdrawn_on: null,
    allowed_actions: actions,
  };
}

/** `GET /v1/portal/deliverables/{id}` by artboard. */
export function deliverable(state: Por09State, id: string): DeliverableOut | undefined {
  if (state === "e" && id === DELIVERABLE_ID.copperleaf) {
    return {
      id,
      kind: "close_package",
      title: "August 2026 financial statements",
      status: "waiting_for_approval",
      restricted_use: false,
      legend_kind: "ar_c_70",
      versions: [version(1, false, 5, ["download"], HASH_V3, "2026-09-14T21:40:00Z")],
    };
  }
  if (id === DELIVERABLE_ID.report && state === "c") {
    return {
      id,
      kind: "auditor_report",
      title: "Independent auditor's report.pdf",
      status: "final",
      restricted_use: false,
      legend_kind: null,
      versions: [version(1, false, 3, ["download"], HASH_V4, "2026-10-09T15:07:00Z")],
    };
  }
  if (id !== DELIVERABLE_ID.fs) return undefined;
  const v3 = version(3, true, 14, ["download", "comment"], HASH_V3, "2026-10-06T14:00:00Z");
  if (state === "a") {
    return {
      id,
      kind: "fs_draft",
      title: "Financial statements",
      status: "for_your_review",
      restricted_use: false,
      legend_kind: null,
      versions: [v3],
    };
  }
  const v4 = (actions: DeliverableVersionOut["allowed_actions"]): DeliverableVersionOut =>
    version(4, true, 14, actions, HASH_V4, "2026-10-08T14:00:00Z");
  if (state === "a2") {
    return {
      id,
      kind: "fs_draft",
      title: "Financial statements",
      status: "for_your_review",
      restricted_use: false,
      legend_kind: null,
      versions: [v3, v4(["download", "comment", "approve"])],
    };
  }
  if (state === "b") {
    return {
      id,
      kind: "fs_draft",
      title: "Financial statements",
      status: "approved_by_you",
      restricted_use: false,
      legend_kind: null,
      versions: [v3, v4(["download"])],
    };
  }
  return {
    id,
    kind: "fs_final",
    title: `${FS_TITLE}.pdf`,
    status: "final",
    restricted_use: false,
    legend_kind: null,
    versions: [version(5, false, 14, ["download"], HASH_V4, "2026-10-09T15:07:00Z")],
  };
}

/** Page comments on draft v3 (a): Dana's question on page 2 and Hannah's answer. */
export const PAGE_COMMENTS: PageCommentsOut = {
  items: [
    {
      id: stableId("page-comment:northwind-fs-v3-1"),
      page: 2,
      line_ref: "Notes receivable from participants",
      author: "Dana Kowalski",
      created_at: "2026-10-06T15:14:00Z",
      body: "Keystone calls these participant loans. Can the note say both?",
    },
    {
      id: stableId("page-comment:northwind-fs-v3-1-reply"),
      page: 2,
      line_ref: "Notes receivable from participants",
      author: "Hannah Leclerc · Brightwater Hale",
      created_at: "2026-10-06T16:02:00Z",
      body: "Yes — Note 5 will read 'Notes receivable from participants (participant loans)'. It will be in draft v4 tomorrow.",
    },
  ],
};
