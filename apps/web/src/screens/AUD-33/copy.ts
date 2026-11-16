// AUD-33 words, verbatim from the handoff (AUD-33 spec.md).
export const COPY = {
  title: "Consolidated trial balance · interim 8/31/2026",
  levelLabel: "Level",
  levels: { one: "Level 1 · Holdings", two: "Level 2 · Operating Co." },
  excel: "Open in Excel",
  locked: "Locked · Omar Haddad · 2:20 PM",
  reopen: "Reopen…",
  pane: "Consolidated",
  levelOneSub: "Level 1 · all five entities",
  levelTwoSub: "Level 2 · Operating Co., Manufacturing, Distribution",
  tabs: "Sheets",
  captionOne:
    "Debits positive, credits in parentheses; every column nets to zero. Statement view: total liabilities 19,600,000 · total equity 31,160,000 (common stock 12,000,000 + retained earnings 15,660,000 + net income 3,500,000) · total liabilities and equity 50,760,000.",
  captionTwo:
    "Manufacturing's 1,200,000 intercompany rent stays at Level 2 and is eliminated at Level 1 (E5). Level 2 feeds Level 1 as one column.",
  tallies: {
    label: "Checks",
    totalAssets: "Total assets",
    netIncome: "Net income · 8 months",
    balanced: "Balanced",
    intercompany: "Intercompany",
    eliminations: "Eliminations",
    mapping: "Mapping",
    afterE4: "0 after E4",
    pending: "Pending",
    tie: "Tie",
    off: (amount: string) => `off ${amount}`,
    posted: (n: number) => `${String(n)} posted`,
  },
  drawer: {
    title: "Eliminations",
    export: "Export",
    add: "New elimination…",
    approveAll: (n: number) => `Approve ${String(n)}…`,
    segment: {
      eliminations: (n: number) => `Eliminations ${String(n)}`,
      adjustments: "Adjustments 0",
    },
    counts: (p: number, a: number, s: number) =>
      `Proposed ${String(p)} · Approved ${String(a)} · Posted ${String(s)}`,
    total: "Total",
    dr: "Dr",
    cr: "Cr",
    adjustmentsEmpty: "No adjustments yet",
    newAdjustment: "+ New adjustment",
    e3Citations: ["Distribution inventory by vendor 8-31-2026.xlsx", "Manufacturing TB 8/31"],
    e3Provenance:
      "Proposed by Accrued Agent 1:31 PM · Approved by Omar Haddad 1:58 PM · Posted 2:01 PM",
    e3Note:
      "Distribution's inventory report tags 1,000,000 as bought from Manufacturing; at Manufacturing's 24.0% margin I propose eliminating 240,000 of unrealized profit.",
    e4Subline:
      "Manufacturing due from Distribution 2,400,000 = Distribution due to Manufacturing 2,400,000 ✓",
  },
  card: {
    level: (n: number) => `Level ${String(n)}`,
    status: { proposed: "Proposed", approved: "Approved", posted: "Posted", rejected: "Rejected" },
    approve: "Approve",
    edit: "Edit",
    reject: "Reject…",
    dr: "Dr",
    cr: "Cr",
    off: (amount: string) => `Off ${amount.replace(/^-/u, "")} · debits ≠ credits`,
  },
} as const;
