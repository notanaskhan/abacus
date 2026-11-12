// F-07-T01 (SPEC-652 AC-6): status words tier 4 needs that C2 does not carry yet, held as kit-local
// draft types during S38 (no status-YAML edit inside the Jan 1 – Apr 20, 2028 window). F-07-T25
// adds them to `docs/product/status-vocabulary.yaml` in the Tue Apr 25, 2028 train, regenerates
// `status.gen.ts`, and removes this file. Nothing outside the tier-4 kits imports it.

/** T13's deadline chip tiers (filing_deadline is not a C2 object yet). Relative to "today". */
export type FilingDeadlineDraftStatus =
  | "overdue" // solid brick
  | "due_7" // ≤ 7 days: red-tint
  | "due_30" // ≤ 30 days: amber-tint
  | "later" // neutral
  | "done" // green-tint with check
  | "postponed" // "Postponed → {date}" (disaster relief)
  | "extended"; // "Extended to {date}"

export const FILING_DEADLINE_DRAFT_LABELS: Readonly<Record<FilingDeadlineDraftStatus, string>> = {
  overdue: "Past due",
  due_7: "Due this week",
  due_30: "Due this month",
  later: "Upcoming",
  done: "Done",
  postponed: "Postponed",
  extended: "Extended",
};

/** Listed for F-07-T25: every draft object and its codes. */
export const DRAFT_STATUS_OBJECTS = {
  filing_deadline: Object.keys(FILING_DEADLINE_DRAFT_LABELS) as FilingDeadlineDraftStatus[],
} as const;
