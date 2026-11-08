// EBP-07 · Form 5500 tie-out & supplemental schedules (A-05-T58): every word verbatim from the
// handoff spec.

export const COPY = {
  title: "Form 5500 Tie-Out",
  agentDraft: "Agent draft",
  edit: "Edit",
  signOff: "Sign off…",
  sourceDocs: "Source Docs",
  tabs: { schedule_h: "Schedule H", part_iv: "Part IV", schedules: "Schedules" },
  uploaded: "Summit draft · uploaded Sep 21",
  tallies: {
    assets: "ASSETS",
    income: "INCOME",
    reconciled: "RECONCILED",
    off: "off",
    tie: "tie",
  },
  columns: {
    line: "Line",
    caption: "Caption",
    fs: "FS",
    form: "Form 5500",
    difference: "Difference",
  },
  groups: {
    assets: "PART I — ASSETS (END OF YEAR)",
    income: "PART II — INCOME AND EXPENSES",
  },
  tick: "✓",
  note: {
    title: "Reconciliation note (draft, FS Note 8)",
    status: "Reconciled — note required",
    send: "Send note to AUD-20",
    body: (fs: string, receivable: string, form: string, fsIncome: string, formIncome: string) =>
      `Net assets available for benefits per the financial statements ${fs} · Less contributions receivable at December 31, 2025 (${receivable}) · Net assets per the Form 5500 ${form}. Net increase per the financial statements ${fsIncome} · Less contributions receivable (${receivable}) · Net income per the Form 5500 ${formIncome}.`,
  },
  footer: { citations: (n: number) => `Citations (${String(n)})`, procedures: "Procedures (1)" },
  partIv: {
    columns: {
      line: "Line",
      question: "Question",
      answer: "Answer on draft",
      amount: "Amount",
      evidence: "Our evidence",
      result: "Result",
    },
    questions: {
      "4a": "Late participant contributions",
      "4b": "Loans or fixed income obligations in default",
      "4d": "Nonexempt transactions",
      "4i": "Schedule of assets held",
      "4j": "Reportable transactions (> 5%)",
    } as Record<string, string>,
    yes: "Yes",
    no: "No",
    inconsistent: "Inconsistent with the late-deposit finding (EBP-04)",
    raise: "Raise exception…",
  },
  schedules: {
    title4i: "Schedule H, line 4i — Schedule of Assets (Held at End of Year)",
    columns: {
      identity: "(b) Identity of issue",
      current: "(e) Current value",
    },
    total: "Total",
    title4a: "Schedule H line 4a",
  },
  empty: {
    title: "Draft Form 5500 not received",
    body: "Summit Plan Administrators uploads it through their request link. The tie-out runs when it arrives.",
    remind: "Remind Summit",
  },
} as const;
