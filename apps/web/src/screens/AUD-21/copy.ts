import paper from "./paper.json";
// AUD-21's words, verbatim from the handoff spec (A-07-T28). The firm's own letter wording comes
// from C11 once the live read lands (A-07-T33); these are the E0 artboard's.

export const COPY = {
  sheet: "Representation letter › Northwind Robotics 401(k) Plan · PY2025",
  tabs: ["Letter", "Signers", "History"] as const,
  general: "General representations (AU-C 580)",
  always: "Always included",
  specific: "Specific representations",
  attachments: "Attachments",
  signerDating: "Signer & dating",
  paperTitle: "Representation letter",
  watermark: "DRAFT",
  send: "Send for signature…",
  requestApproval: "Request partner approval…",
  remind: "Remind…",
  redate: "Start re-date…",
  edit: "Edit",
  preview: "Preview as client",
  drafting: "Accrued Agent is drafting from the findings register (9 findings) and the SUM",
  helper: "If the signature date is not October 9, 2026, Accrued starts the re-date flow.",
} as const;

export const GENERAL = [
  "Financial statements and the §103(a)(3)(C) election",
  "Information and access provided",
  "All transactions recorded",
  "Internal control and fraud",
  "Laws and regulations, including ERISA",
  "Related parties and parties in interest",
  "Subsequent events",
  "Uncorrected misstatements (SUM attached)",
  "Litigation and claims",
] as const;

export interface Specific {
  key: string;
  label: string;
  reason: string;
  on: boolean;
}

export const SPECIFIC: readonly Specific[] = [
  {
    key: "certification",
    label: "Certification by Harborline Trust Company",
    reason: "Engagement letter election · Note 4",
    on: true,
  },
  {
    key: "late_contributions",
    label: "Late participant contributions",
    reason: "F-01 · Dec 26 payroll · lost earnings $64.38 · VFCP SCC",
    on: true,
  },
  {
    key: "missed_deferrals",
    label: "Missed deferrals for 4 auto-enrolled participants",
    reason: "F-03 · RN-14",
    on: true,
  },
  {
    key: "compensation",
    label: "Compensation definition and corrective match",
    reason: "F-07 · PAJE-1",
    on: true,
  },
  {
    key: "accrued_admin",
    label: "Accrued administrative expenses",
    reason: "F-08 · PAJE-2",
    on: true,
  },
  {
    key: "loan_offsets",
    label: "Loan offsets presented as benefits paid",
    reason: "F-06 · RJE-1",
    on: true,
  },
  {
    key: "plan_provisions",
    label: "Plan provisions and amendments",
    reason: "Note 11 · SECURE 2.0 amendment",
    on: true,
  },
  {
    key: "form_5500",
    label: "Form 5500 prepared by Summit Plan Administrators",
    reason: "EBP-07",
    on: true,
  },
  { key: "tax_status", label: "Tax status", reason: "Note 7", on: true },
  {
    key: "going_concern",
    label: "Going concern",
    reason: "No conditions identified (AUD-19)",
    on: false,
  },
];

/** The paper's plan-specific paragraphs, keyed by the toggle that includes them (12–15). */
export const PLAN_PARAGRAPHS: readonly { key: string; text: string }[] = [
  {
    key: "late_contributions",
    text: "Participant contributions of $33,540 withheld from the December 26, 2025 payroll were remitted on January 9, 2026. Lost earnings of $64.38 were deposited on September 30, 2026 under the Voluntary Fiduciary Correction Program Self-Correction Component. There were no other late remittances.",
  },
  {
    key: "missed_deferrals",
    text: "We will correct the missed deferrals of four auto-enrolled participants under EPCRS.",
  },
  {
    key: "compensation",
    text: "We will correct, under EPCRS, the safe-harbor matching contributions that were not computed on bonus pay as the plan's definition of compensation requires.",
  },
  {
    key: "loan_offsets",
    text: "Loans of three terminated participants totaling $14,850 were offset and reported as distributions.",
  },
];

// AUD-21 a: the letter as Northwind's plan administrator signs it. The wording is the firm's
// representation-letter template (content, not code: A-07-T12), so it lives in data beside the
// screen until the composed letter arrives from the API.
export const PAPER: Readonly<typeof paper> = paper;
