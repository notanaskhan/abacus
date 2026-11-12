// TXI-02 copy and the Ridgeline K-1 the artboards draw (T-04-T40; handoff TXI-02 spec, verbatim).
// The figures tie: 141,634 + 96,989 + 69,277 = 307,900; 7,011 + 4,268 + 4,746 = 16,025; 61,580 =
// 20% × 307,900 < 98,450; outside basis 1,912,500 + 2,762,075 = 4,674,575 (4,676,125 after
// Ridgeline's M-2 fix). Figures are the server's (code's), never summed in the browser (ADR-050).

export type Frame = "a" | "b" | "c" | "d" | "e";
export const FRAMES: readonly Frame[] = ["a", "b", "c", "d", "e"];

export interface Treatment {
  n: number;
  key: string;
  label: string;
  resolved: string;
  rationale: string;
  chip?: string; // the citation chip: the K-1 region it lights
  saly: string;
  changed?: boolean; // amber "Changed vs 2024"
  approved?: string; // green-tint "Approved · SI 9:31"
  statementRow?: string; // the PTET statement row it lights
}

export const COPY = {
  subbar: {
    checkpoints: "☰ Checkpoints",
    sync: "Out of sync",
    form: "2025 Form 1040",
    client: "Jonah & Claire Feld",
    state: "In review · Manager",
    assistant: "Assistant",
  },
  tabs: ["Overview", "Intake 2", "Review 37", "Issues 3", "Activity"],
  back: "‹ Sch E – K-1",
  title: "K-1 treatments · Ridgeline Property Partners, LP",
  draftChip: "Draft K-1 · pre-release",
  releasedChip: "Released Sep 15",
  cardTitle: "Schedule K-1 (Form 1065) · Jonah Feld · 25%",
  columns: ["Treatment", "Resolved (2025)", "Rationale", "2024 (SALY)", "Status"],
  proposed: "Proposed",
  changed: "Changed vs 2024",
  approvedRow: "Approved · SI",
  overridden: "Overridden · SI",
  approvalTitle: "Approve 7 treatments",
  reasoningLabel: "Reasoning",
  reasoning:
    "Treatments 1–6 match the 2024 return and the draft K-1. Treatment 7 changes because Ridgeline elected PTET in Colorado and New York for 2025; the credits flow to the Colorado nonresident return and IT-653. Box amounts are not expected to change when the final K-1 is released.",
  source: "2025 Schedule K-1 (Draft) · 6 citations",
  reject: "Reject…",
  edit: "Edit…",
  approve: "✓ Approve treatments",
  approvedLine: "✓ Approved by Samuel Ito · 10:24 AM · checkpoint 'K-1 treatments'",
  changedNote:
    "New Colorado and New York PTET credits — confirm the Colorado nonresident filing is still required",
  overrideOptions: ["Passive", "Nonpassive"],
  reasonLabel: "Reason",
  reasonRequired: "A reason is required",
  save: "Save override",
  released:
    "Final K-1 matches the draft on every treated box; Item L 1,914,050; outside basis 4,676,125",
  viewerFile: "Ridgeline_2025_PTET_Statement_JonahFeld_DRAFT.pdf",
  viewerPage: "PTET statement — partner share",
  pages: "1 / 1",
} as const;

/** The K-1 card's rows (label, value). */
export const K1_ROWS: readonly (readonly [string, string])[] = [
  ["Net rental real estate income (box 2)", "$307,900"],
  ["Interest income (box 5)", "$4,600"],
  ["Tax-exempt interest (box 18A)", "$1,550"],
  ["Distributions (box 19A)", "$150,000"],
  ["§199A (box 20 Z) QBI", "$307,900"],
  ["UBIA", "$3,938,000"],
  ["State", "IL / CO / NY"],
];

/** The chip cloud; the amber one changed vs 2024. */
export const CHIPS: readonly { label: string; changed?: boolean }[] = [
  { label: "Passive activity" },
  { label: "Not a PTP" },
  { label: "§199A eligible" },
  { label: "NII (Form 8960)" },
  { label: "At-risk: QNF" },
  { label: "State IL 46.0 · CO 31.5 · NY 22.5" },
  { label: "PTET credits IL · CO · NY", changed: true },
  { label: "Form 1040 line 2a + IT-201 line 20" },
];

export const TREATMENTS: readonly Treatment[] = [
  {
    n: 1,
    key: "passive",
    label: "Passive / nonpassive",
    resolved: "Passive",
    rationale: "Limited partner; no material participation (Reg. §1.469-5T(e)(2))",
    chip: "K-1 · G",
    saly: "Passive",
  },
  {
    n: 2,
    key: "ptp",
    label: "Publicly traded partnership",
    resolved: "Not a PTP",
    rationale: "Box D unchecked",
    chip: "K-1 · D",
    saly: "Not a PTP",
  },
  {
    n: 3,
    key: "qbi",
    label: "§199A",
    resolved: "Eligible — QBI 307,900; deduction 61,580",
    rationale:
      "Statement A reports a rental real estate trade or business; W-2 wages 0; UBIA 3,938,000 → limit 98,450 > 20% of QBI",
    chip: "Stmt A",
    saly: "Eligible — 56,320",
  },
  {
    n: 4,
    key: "niit",
    label: "Net investment income",
    resolved: "Included — 307,900 + 4,600",
    rationale: "Passive rental and portfolio interest (Form 8960)",
    saly: "Included",
  },
  {
    n: 5,
    key: "basis",
    label: "Basis and at-risk",
    resolved: "Sufficient — outside basis 4,674,575",
    rationale:
      "Tax capital 1,912,500 + §752 share 2,762,075 (qualified nonrecourse 2,678,125); 4,676,125 after Ridgeline's M-2 fix",
    chip: "Basis sched.",
    saly: "Sufficient",
  },
  {
    n: 6,
    key: "state",
    label: "State sourcing",
    resolved: "IL 141,634 · CO 96,989 · NY 69,277",
    rationale:
      "By property: Elm Street (IL) 46.0% · Larimer Lofts (CO) 31.5% · Bergen Street (NY) 22.5%; total 307,900",
    chip: "State K-1",
    saly: "IL 46.0 · CO 31.5 · NY 22.5",
  },
  {
    n: 7,
    key: "ptet",
    label: "PTET credits",
    resolved: "IL 7,011 · CO 4,268 · NY 4,746",
    rationale:
      "25% of entity PTET 28,044 / 17,070 / 18,982; CO and NY elected for the first time in 2025",
    chip: "PTET stmt",
    saly: "IL 6,412 only",
    changed: true,
  },
  {
    n: 8,
    key: "tax_exempt",
    label: "Tax-exempt interest",
    resolved: "Form 1040 line 2a 1,550 · NY addition 1,550",
    rationale: "Municipal bond fund with 0% New York obligations",
    chip: "Stmt p. 3",
    saly: "2a 1,400 · NY addition 1,400",
    approved: "Approved · SI 9:31",
  },
];

/** The viewer's PTET statement rows (key, label, figure); the selected treatment lights its row. */
export const STATEMENT: readonly { key: string; label: string; figure: string }[] = [
  { key: "IL", label: "Illinois PTET 28,044 × 25%", figure: "7,011" },
  { key: "CO", label: "Colorado PTET 17,070 × 25%", figure: "4,268" },
  { key: "NY", label: "New York PTET 18,982 × 25%", figure: "4,746" },
  { key: "total", label: "Total", figure: "16,025" },
];

/** Treatment 5 in the released state (the final K-1 picked up Ridgeline's M-2 fix). */
export const RELEASED_BASIS = "Sufficient — outside basis 4,676,125";
