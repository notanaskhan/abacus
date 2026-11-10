// AUD-25's words and data, verbatim from the handoff spec and revision R2
// (`AUD-25 Assembly and archive/spec.md`, `revision.md`). Fixture mode only (A-07-T39): the live
// screen reads A-07-T31's `GET …/archive` and T37's lock and manifest.

export type Frame = "a" | "b" | "b2" | "c" | "d" | "e";
export const FRAMES: readonly Frame[] = ["a", "b", "b2", "c", "d", "e"];

export const TITLE = "Assembly & archive";
export const RELEASED = "Released Oct 9, 2026";
export const PILL = {
  days: "Archive in 47 days",
  risk: "Archive in 5 days",
  locked: "Locked · WORM",
} as const;

export const REQUEST_LOCK = "Request lock…";
export const REQUEST_TIP = "1 checklist item open";
export const LOCK = "Lock archive…";
export const ROLL = {
  archiveAndRoll: "Archive and roll forward…",
  tip: "Available once the archive can be locked (8 of 9)",
  roll: "Roll forward…",
} as const;

export const CLOCK = {
  days: "47 days",
  riskDays: "5 days",
  until: "until the documentation completion date",
  rows: [
    ["Report released", "Oct 9, 2026"],
    ["Assembly deadline", "Dec 8, 2026 · AU-C 230 · 60 days"],
    ["Retention", "Until Oct 9, 2033 · BH policy 7 years (AU-C 230 minimum 5)"],
    ["Legal hold", "None"],
  ],
  elapsed: "13 of 60 days elapsed",
  elapsedPct: 22,
} as const;

export const LOCKED_LINE = "Locked Dec 3, 2026 · 4:18 PM · Hannah Leclerc · seal 7c41…a9e2 · G9 ✓";

export const CHECKLIST_TITLE = "Archive checklist";
export interface Item {
  title: string;
  evidence: string;
  open?: boolean;
  chip?: string;
}
export const CHECKLIST: readonly Item[] = [
  {
    title: "All workpapers signed",
    evidence: "26 of 26 · partner 13 of 13 · EQR 6 of 6",
    chip: "AUD-17",
  },
  {
    title: "Review notes resolved",
    evidence: "14 of 14 cleared · history retained (BH policy)",
    chip: "AUD-17",
  },
  {
    title: "Versions handled",
    evidence:
      "Superseded versions kept: Materiality v1–v3 · Sample Selection v1–v2 · Plan Review v1–v2",
  },
  {
    title: "Binder index complete",
    evidence: "Built by Accrued Agent · run #4302 · reviewed by MD",
  },
  {
    title: "Final report and deliverables filed",
    evidence: "Released Oct 9 · 3 deliverables",
    chip: "AUD-24",
  },
  {
    title: "Governance communications filed",
    evidence:
      "AU-C 260 planning ✓ · AU-C 260 completion ✓ · AU-C 265/703 letter — Draft, due Dec 8",
    open: true,
    chip: "AUD-22",
  },
  { title: "Independence confirmations filed", evidence: "5 of 5 through Oct 9" },
  { title: "Agent run logs packaged", evidence: "23 runs · traces and citations" },
  {
    title: "Form 5500 filing confirmation",
    evidence: "Filed Oct 14, 2026 · EFAST2 acknowledgment",
  },
];
/** Once the governance letter is sent and filed (states b onward). */
export const GOVERNANCE_DONE =
  "AU-C 260 planning ✓ · AU-C 260 completion ✓ · AU-C 265/703 letter ✓";

export const BINDER_TITLE = "Binder index";
export const BINDER_HEAD = ["Section", "Contents", "Items"] as const;
export const BINDER: readonly (readonly [string, string, string])[] = [
  ["A Planning", "Trial balance to service organizations & SOC 1", "6"],
  ["B Fieldwork", "Plan review, sample selection, investments & certification", "3"],
  ["C Testing", "Eligibility to Form 5500 tie-out", "7"],
  [
    "D Completion",
    "Findings, SUM, final analytics, subsequent events, going concern, checklist",
    "6",
  ],
  ["E Reporting", "FS, rep letter, governance letters, report", "4"],
  ["Total workpapers", "", "26"],
  ["F Source documents", "", "24"],
  ["G Agent run logs", "", "23"],
  ["H Independence confirmations", "", "5"],
];

export const ADDITIONS = {
  title: "Post-lock additions",
  empty: "No additions.",
  emptyBody:
    "After the lock, additions need a reason and engagement partner approval. The original stays unchanged.",
  add: "+ Add after lock…",
  pill: "Addition logged",
  row: "Jan 15, 2027 · Alternative-procedure memo for the omitted bring-down inquiry (PI-02) · added by Hannah Leclerc · approved by Margaret Okonkwo · reason 'AU-C 585 omitted procedure'",
} as const;

export const SHEET = {
  title: "Lock the archive",
  body: "Contents become read-only and are sealed with a SHA-256 hash",
  attest: "Assembly is complete",
  roll: "Then roll forward to PY2026 (ENG-13)",
  cancel: "Cancel",
  confirm: "Lock archive",
} as const;

export const DOCK = {
  title: "Agent",
  run: "Archive readiness checker · run #4302 · Oct 22, 9:14 AM",
  narration:
    "I built the binder index from the engagement record: 26 workpapers, 24 source documents, 23 agent run logs and 5 independence confirmations. 8 of 9 checklist items are complete. The open item is the AU-C 265 and AU-C 703 letter, which is a draft due December 8. The archive can be locked once it is sent and filed.",
  lockedNarration:
    "The archive is locked. Roll-forward can carry the structure, fund mappings, beginning balances 16,861,000, the 24-request list and 2 triggers; prior-year evidence is referenced, never copied.",
  tools: [
    "Execute › Build binder index",
    "Execute › Package agent run logs",
    "Execute › Verify sign-offs and hashes",
  ],
  composer: "Message",
} as const;
