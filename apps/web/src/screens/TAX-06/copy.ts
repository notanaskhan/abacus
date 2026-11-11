// TAX-06 copy and the Feld issue data the artboards draw (T-04-T26; handoff TAX-06 spec,
// verbatim). Counts: 4 open = 2 Missing information + 1 Action required + 1 Review point; 3
// resolved; 7 raised Aug 25. The 18A ghost values are the agent's proposal (1,550 on Form 1040
// line 2a and IT-201 line 20), never a value until a person approves it in SHL-10.

export type Frame = "a" | "b" | "c" | "d" | "e" | "f" | "g" | "loading";
export const FRAMES: readonly Frame[] = ["a", "b", "c", "d", "e", "f", "g", "loading"];

export type Severity = "high" | "medium";
export interface IssueRow {
  key: string;
  title: string;
  kind: string;
  severity: Severity;
  group: string;
  sub: string;
  agentCanFix?: boolean;
  resolved?: { on: string; note: string };
}

export const OPEN: readonly IssueRow[] = [
  {
    key: "draftK1",
    title: "Ridgeline K-1 is a draft — final approval blocked until Ridgeline is approved",
    kind: "Action required",
    severity: "high",
    group: "Income",
    sub: "Sch E, p 2 - Partnership Passthrough (K-1 1065)",
  },
  {
    key: "box18a",
    title: "Source K-1 box 18A 'Tax-exempt interest' is not on the worksheet",
    kind: "Missing information",
    severity: "high",
    group: "Income",
    sub: "Sch E, p 2 - Partnership Passthrough (K-1 1065)",
    agentCanFix: true,
  },
  {
    key: "estimates",
    title: "Obtain 2025 federal and NY estimated tax payment confirmations",
    kind: "Missing information",
    severity: "medium",
    group: "Payments/Penalties/Estimates",
    sub: "Payments",
  },
  {
    key: "nycResidency",
    title: "Confirm full-year NYC residency for the IT-201 resident tax",
    kind: "Review point",
    severity: "medium",
    group: "State",
    sub: "New York",
  },
];

export const RESOLVED: readonly IssueRow[] = [
  {
    key: "digitalAssets",
    title: "Confirm digital asset transactions for Form 1040",
    kind: "Missing information",
    severity: "medium",
    group: "General",
    sub: "Basic Data",
    resolved: { on: "Aug 27", note: "Claire answered No" },
  },
  {
    key: "nysRefund",
    title: "2025 Form 1099-G — confirm taxability of the NY refund",
    kind: "Review point",
    severity: "medium",
    group: "Income",
    sub: "Other Income (1099-G)",
    resolved: { on: "Aug 27", note: "not taxable: 2024 SALT limited to $10,000" },
  },
  {
    key: "refundAccount",
    title: "Refund bank account required — paper refund checks ended Sep 30, 2025",
    kind: "Missing information",
    severity: "medium",
    group: "General",
    sub: "Basic Data",
    resolved: { on: "Aug 28", note: "" },
  },
];

export interface Detail {
  body: string;
  assignedTo: string;
  priority: "High" | "Medium";
  createdBy: string;
  kindPill?: string;
  blocks?: string;
  linked: string;
  chip?: string;
  primary: string;
  note?: string;
  resolveDisabled?: string;
}

export const DETAILS: Record<string, Detail> = {
  box18a: {
    body: "The source document reports 18A Tax-exempt interest = 1,550, but no worksheet field carries that amount. It belongs on Form 1040 line 2a and, because the fund holds no New York obligations, as a New York addition on IT-201 line 20. Confirm the box was intentionally omitted, or add it before export.",
    assignedTo: "Accrued Agent",
    priority: "High",
    createdBy: "Accrued Agent",
    linked:
      "2025 K-1 (Form 1065) · Jonah Feld · Ridgeline Property Partners, LP · Draft K-1 · pre-release",
    chip: "Ridgeline_2025_K1_JonahFeld_DRAFT.pdf",
    primary: "Set Fix Instructions",
  },
  draftK1: {
    body: "",
    assignedTo: "Samuel Ito",
    priority: "High",
    createdBy: "Accrued Agent",
    blocks:
      "Final approval (BH-TAX-02, Daniel Reyes) and export to CCH Axcess. The Ridgeline 2025 Form 1065 is In review · Partner, due Sep 15. Its Schedule M-2 is off 6,200; when fixed, Jonah's Item L ending capital becomes 1,914,050 (draft 1,912,500). Boxes 2, 5 and 18A are not expected to change.",
    linked: "2025 Form 1065 · Ridgeline Property Partners, LP",
    primary: "Open Ridgeline 1065",
    resolveDisabled: "Resolves when the final K-1 is released",
  },
  estimates: {
    body: "The organizer reports 2025 federal estimates of 60,000 (4 × 15,000) and NY estimates of 14,000 (4 × 3,500). No confirmations are in the binder, so Form 1040 line 26 and IT-201 line 75 are carried from the organizer.",
    assignedTo: "Kevin Osei",
    priority: "Medium",
    createdBy: "Accrued Agent",
    kindPill: "Waiting on client",
    linked: "2025 tax organizer — Claire Feld",
    primary: "Ask the client…",
    note: "Requested Sep 1 · Claire Feld is uploading 2 files now",
  },
  nycResidency: {
    body: "Halvard Securities mailed the 2025 1099 to 41 Mill Road, Rhinebeck, NY from Jul 1, 2025. Claire's answers (Sep 9) show the Brooklyn co-op remained the family home: 281 days in New York City, 72 in Rhinebeck, 12 traveling. The draft treats both spouses as full-year New York State and City residents (NYC resident tax 23,014).",
    assignedTo: "Kevin Osei",
    priority: "Medium",
    createdBy: "Accrued Agent",
    linked: "Residency answers — Claire Feld",
    primary: "Open residency workpaper",
  },
};

export const SELECTED: Record<Frame, string | null> = {
  a: "box18a",
  b: "draftK1",
  c: "estimates",
  d: "nycResidency",
  e: "box18a",
  f: null,
  g: null,
  loading: null,
};

/** The sheets pane (Ridgeline worksheet): ghost values are the agent's proposal. */
export const SHEET_ROWS: readonly { label: string; value?: string; ghost?: string }[] = [
  { label: "Ordinary business income", value: "0" },
  { label: "Net rental real estate income", value: "307,900" },
  { label: "Interest income", value: "4,600" },
  { label: "Tax-exempt interest (Form 1040 line 2a)", ghost: "1,550" },
  { label: "Distributions", value: "150,000" },
];
export const STATE_ROWS: readonly { label: string; value?: string; ghost?: string }[] = [
  { label: "NY addition — IT-201 line 20", ghost: "1,550" },
  { label: "NYS amount", value: "69,277" },
];

export const COPY = {
  title: "Feld 2025 Form 1040",
  client: "Jonah & Claire Feld",
  tabs: (open: number) => [
    "Overview",
    "Intake 2",
    "Review 37",
    `Issues ${String(open)}`,
    "Activity",
  ],
  pane: "Issues",
  queueHead: "Open Issues",
  queueSub: "Instructions Required",
  addInstructions: "+ Instructions…",
  addIssue: "+ Issue…",
  download: "Download issues as CSV",
  explain: "Explain…",
  resolve: "Mark as Resolved",
  resolveNoteRequired: "Add a note to mark this as resolved",
  accept: "Accept",
  reject: "Reject",
  rejectReasons: ["Not supported by the source", "Wrong field", "Already on the return", "Other"],
  fixInstruction: "Add 1,550 to line 2a and IT-201 line 20",
  inProgress: "In progress",
  running: "Adding 1,550 to Form 1040 line 2a · Running",
  resolvedPill: "Resolved",
  emptyTitle: "No open issues.",
  emptyBody: "Issues raised by the agent or reviewers appear here.",
  whatItBlocks: "What it blocks",
  linkedEntities: "Linked Entities",
  sheetsSection: "Income and Adjustments",
  stateSection: "State Allocation",
  viewer: "Ridgeline_2025_K1_JonahFeld_DRAFT.pdf",
  region: "18 Tax-exempt income and nondeductible expenses · A 1,550",
  loading: "Loading issues",
  csvHeader: "Title,Kind,Priority,Status,Group",
} as const;

/** The CSV the Download button builds (TAX-06; the API's export is the live one). */
export function issuesCsv(rows: readonly IssueRow[]): string {
  const cell = (raw: string): string => {
    const v = /^[=+\-@\t\r]/.test(raw) ? `'${raw}` : raw; // a spreadsheet never evaluates it
    return /[",\n]/.test(v) ? `"${v.replace(/"/g, '""')}"` : v;
  };
  return [
    COPY.csvHeader,
    ...rows.map((r) =>
      [
        r.title,
        r.kind,
        r.severity === "high" ? "High" : "Medium",
        r.resolved ? "Resolved" : "Open",
        r.group,
      ]
        .map(cell)
        .join(","),
    ),
  ].join("\n");
}
