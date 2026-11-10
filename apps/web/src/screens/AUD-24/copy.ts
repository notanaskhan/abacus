// AUD-24's words and data, verbatim from the handoff spec (`AUD-24 Issuance and release/spec.md`).
// Fixture mode only (A-07-T38): the live screen reads A-07-T30's `GET …/release` and T36's filings.

export type Frame = "a" | "b" | "c" | "d" | "e" | "f";
export const FRAMES: readonly Frame[] = ["a", "b", "c", "d", "e", "f"];

export const TITLE = "Issuance & release";
export const REPORT_DATE = "Report date Oct 9, 2026";
export const PILL = {
  ready: "Ready to release",
  completion: "Completion",
  released: "Released Oct 9",
} as const;

export interface Gate {
  gate: "G5" | "G6" | "G7";
  title: string;
  rows: readonly (readonly [string, string, string])[]; // label, value, link target
}

export const GATES: readonly Gate[] = [
  {
    gate: "G5",
    title: "Reviewed",
    rows: [
      ["Workpapers", "26 of 26 prepared and reviewed", "AUD-17"],
      ["Partner sign-offs", "13 of 13 required", "AUD-17"],
      ["EQR sign-offs", "6 of 6", "AUD-17"],
      ["Review notes", "0 open · 14 cleared", "AUD-17"],
      ["Changed after sign-off", "0", "AUD-17"],
    ],
  },
  {
    gate: "G6",
    title: "EQR concurred",
    rows: [
      ["Reviewer", "Thomas Whitcombe", "AUD-18"],
      ["Concurred", "Oct 5, 2026 · 4:40 PM", "AUD-18"],
      ["EQR notes", "2 of 2 cleared", "AUD-18"],
    ],
  },
  {
    gate: "G7",
    title: "Represented",
    rows: [
      ["Signed by", "Dana Kowalski · Plan Administrator", "AUD-21"],
      ["Signed", "Oct 9, 2026 · 9:12 AM", "AUD-21"],
      ["Letter dated", "October 9, 2026 = report date ✓", "AUD-21"],
      ["SUM attached", "2 items · immaterial", "AUD-21"],
    ],
  },
];

export const MET = "✓ Met";
export const NOT_MET = "Not met";
export const G7_BLOCKED = "Out for signature since Oct 6";

export const ALSO_TITLE = "Also required before release";
export const ALSO: readonly (readonly [string, string, string])[] = [
  ["Final FS approved by management", "Dana Kowalski · Oct 8 (POR-09)", "AUD-20"],
  ["Report approved by the engagement partner", "Oct 7", "AUD-23"],
  [
    "Subsequent events through report date",
    "run #4240 · Oct 9, 9:04 AM · no new events",
    "AUD-19",
  ],
  ["Independence reconfirmed", "5 of 5 · Oct 9", "AUD-19"],
  ["Final materiality", "v3 · no change", "AUD-19"],
  ["AU-C 260 completion communication", "Sent Oct 8", "AUD-22"],
];

export const G8 = {
  pending: "G8 · Released — recorded when you release",
  body: "Release applies the Brightwater Hale signature, delivers the pack, and starts two clocks: archive by Dec 8, 2026 (AU-C 230, 60 days) and the AU-C 265 letter by Dec 8, 2026.",
  done: "Released Oct 9, 2026 · 10:07 AM · Margaret Okonkwo",
  clock: "Archive in 60 days · by Dec 8, 2026",
} as const;

export const BAR = {
  left: "Report date October 9, 2026 · Chicago, Illinois",
  button: "Release report…",
  reserved: "Reserved to the engagement partner",
  blocked: "Blocked by G7 · representation letter",
  nonPartner: "Only Margaret Okonkwo can release this report",
} as const;

export const DIALOG = {
  title: "Release report",
  rows: [
    ["Engagement", "Northwind Robotics 401(k) Plan · PY2025"],
    ["Report date", "Oct 9, 2026"],
    ["Signature", "Brightwater Hale LLP"],
    ["Recipients", "Dana Kowalski (POR-09) · Benefits Committee (POR-15)"],
  ],
  attest: "I am the engagement partner and I authorize release of this report",
  cancel: "Cancel",
  confirm: "Release report",
} as const;

export const TOAST = "Report released · delivered to Dana Kowalski";

export const DOCK = {
  title: "Deliverables",
  pack: "Deliverable pack",
  delivery: "Delivery",
  filings: "Filings",
} as const;

export interface FileRow {
  name: string;
  meta: string;
  pill: string;
  tone: "muted" | "green-tint" | "amber";
}

export const FILES: readonly FileRow[] = [
  {
    name: "Independent auditor's report.pdf",
    meta: "3 pages · signature applied at release",
    pill: "At release",
    tone: "muted",
  },
  {
    name: "Financial statements and supplemental schedules.pdf",
    meta: "14 pages · v3",
    pill: "Final",
    tone: "green-tint",
  },
  {
    name: "AU-C 260 communication — Benefits Committee.pdf",
    meta: "Sent Oct 8",
    pill: "Sent",
    tone: "green-tint",
  },
  {
    name: "AU-C 265 and AU-C 703 letter",
    meta: "Draft · due Dec 8, 2026",
    pill: "Due Dec 8",
    tone: "amber",
  },
];
export const DELIVERED = "Delivered";

export const DELIVERY: readonly (readonly [string, string])[] = [
  ["Portal deliverables", "Dana Kowalski (POR-09)"],
  ["Governance room", "Benefits Committee (POR-15)"],
];

export const FILING = {
  title: "Form 5500 with Schedule H and auditor's report",
  filer: "Filer: Northwind Robotics, Inc. · prepared by Summit Plan Administrators · EFAST2",
  due: "Due Oct 15, 2026 (Form 5558)",
  awaiting: "Awaiting client filing",
  filed: "Filed Oct 14, 2026 · EFAST2 acknowledgment received",
} as const;
