// TAX-08 copy and the Feld data the assistant artboards draw (T-04-T34; handoff TAX-08 spec,
// verbatim). Ties: 598,030 + 1,550 + 16,025 = 615,605 (before the fix 598,030 + 0 + 16,025 =
// 614,055); 20% × 307,900 = 61,580 < 2.5% × 3,938,000 = 98,450; federal tax unchanged. The agent
// proposes; Samuel Ito approves. g and h (saved prompts) are W-03's and stay hidden here.

export type Frame = "a" | "a2" | "b" | "c" | "d" | "e" | "f" | "loading" | "notAllowed";
export const FRAMES: readonly Frame[] = [
  "a",
  "a2",
  "b",
  "c",
  "d",
  "e",
  "f",
  "loading",
  "notAllowed",
];

export const VIEWER = "Samuel Ito";

export const COPY = {
  title: "Assistant",
  close: "Close the assistant",
  history: "History",
  newThread: "New thread",
  context: "2025 Form 1040 · Feld · 41 documents · 4 open issues · pro forma 2025I:FeldJ:V3",
  composer: "Ask about this return…",
  send: "Send",
  question:
    "Is the Ridgeline K-1 still passive and §199A-eligible this year, and what's missing before I can clear it?",
  answer:
    "Yes on both. Jonah is a limited partner with no material participation, so the Ridgeline rental activity stays passive; the 2024 return treated it the same way. The draft K-1 Statement A reports the rentals as a §199A trade or business with UBIA of 3,938,000 for Jonah's 25%, so the QBI deduction is 61,580 (20% of 307,900), under the 98,450 UBIA limit.",
  k1Head: "Schedule K-1 · Ridgeline Property Partners, LP",
  draftPill: "Draft K-1 · pre-release",
  closing:
    "One gap: box 18A (1,550) is not on the worksheet. I've prepared the change below; it does not change federal tax.",
  cardTitle: "Proposed change · creates a checkpoint",
  reasoningHead: "Reasoning",
  reasoning:
    "The K-1 reports 1,550 of tax-exempt interest from a municipal bond fund that holds no New York obligations. It belongs on Form 1040 line 2a and, as interest on other states' bonds, on IT-201 line 20. Federal tax does not change; New York AGI rises by 1,550. The rest of the return keeps its current treatment.",
  source: "2025 Schedule K-1 (Draft)",
  sourceMeta: "2 citations",
  policy: "No change to federal tax · reviewer approval required",
  reject: "Reject…",
  edit: "Edit…",
  approveObject: "adjustments",
  thinking: "Reading 41 documents, 3 workpapers and the 2024 return…",
  applied: "✓ Approved by Samuel Ito · 9:31 AM · checkpoint 'K-1 box 18A'",
  undo: "Undo",
  toast: "Checkpoint created",
  rejected: "Rejected by Samuel Ito · reason: wait for the final K-1",
  rejectReason: "Reason",
  followUpAnswer:
    "Total tax rose 12,397: tax +11,150 (Schedule E +26,300 and wages +17,400 leave 88,559 of ordinary income in the 32% bracket, against 61,150 in 2024) and other taxes +1,247 (NIIT +1,090, Additional Medicare Tax +157).",
  followUpQuestion: "Explain the change in total tax vs 2024",
  notAllowed: "This return isn't available.",
  loading: "Loading the assistant",
  txi02: "Opens TXI-02 (later)",
  tax06: "Box 18A is not on the worksheet · open issue in TAX-06",
} as const;

export interface K1Row {
  key: string;
  label: string;
  value: string;
  /** The viewer region the row lights (K-1 page 2). */
  region: string;
}

export const K1_ROWS: readonly K1Row[] = [
  { key: "rental", label: "Net rental real estate income", value: "$307,900", region: "2" },
  { key: "interest", label: "Interest income", value: "$4,600", region: "5" },
  { key: "taxExempt", label: "Tax-exempt interest", value: "$1,550", region: "18A" },
  { key: "state", label: "State", value: "IL / CO / NY", region: "state" },
];
/** The row the answer is about: lit purple on a and a2. */
export const LIT_ROW = "taxExempt";

export const CHIPS: readonly string[] = [
  "Passive",
  "Not a PTP",
  "§199A eligible",
  "NII (Form 8960)",
  "State IL · CO · NY",
  "PTET credits IL 7,011 · CO 4,268 · NY 4,746",
];

export interface DiffLine {
  key: string;
  label: string;
  before: string;
  after: string;
}

export const DIFF: readonly DiffLine[] = [
  {
    key: "f1040_2a",
    label: "Form 1040 line 2a — Tax-exempt interest",
    before: "0",
    after: "1,550",
  },
  {
    key: "it201_20",
    label: "IT-201 line 20 — Interest on other states' obligations",
    before: "0",
    after: "1,550",
  },
  { key: "it201_33", label: "IT-201 line 33 — New York AGI", before: "614,055", after: "615,605" },
];

export const FOLLOW_UPS: readonly string[] = [
  "Summarize what's left before partner review",
  "Explain the change in total tax vs 2024",
  "Draft the Rhinebeck question for Claire",
];

export const IDLE_PROMPTS: readonly string[] = [
  "What's left before partner review?",
  "Explain the 2025 vs 2024 change in total tax",
  "Which documents haven't been approved at manager level?",
];

export interface YearRow {
  label: string;
  y2024: string;
  y2025: string;
}

export const FOLLOW_UP_TABLE: readonly YearRow[] = [
  { label: "Total tax", y2024: "110,826", y2025: "123,223" },
  { label: "Tax", y2024: "99,381", y2025: "110,531" },
  { label: "Other taxes", y2024: "11,445", y2025: "12,692" },
];

/** The ties the artboards rest on, as whole dollars (code's, checked by the test). */
export const TIES = {
  nyAgiBefore: { parts: [598030, 0, 16025], total: 614055 },
  nyAgiAfter: { parts: [598030, 1550, 16025], total: 615605 },
  qbi: { box2: 307900, rate: 20, deduction: 61580, ubia: 3938000, ubiaRate: 2.5, limit: 98450 },
  totalTax: { y2024: 110826, y2025: 123223, rise: 12397 },
} as const;
