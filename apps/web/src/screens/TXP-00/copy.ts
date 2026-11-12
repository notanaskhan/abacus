// TXP-00 · Return › Agent (entity returns): the handoff's words, verbatim (spec.md A to E).

// Section keys name a form part, never a credential (secrets_scan SECRET-003).
const INTERIM_706D = "interim_closing_706d";
const CAPITAL_M2 = "capital_m2";
const FEDERAL_K1S = "federal_k1s";
const STATE_K1S_K3S = "state_k1s_k3s";

export const COPY = {
  rail: "General Information",
  links: "Links",
  team: "Team",
  workbook: "Workbook",
  composer: "Ask the workbook agent…",
  viewWork: "View work",
  run: "Run",
  runMenu: "Run ⌄",
  // The handoff's "▶ Run": the glyph is the play icon beside the word (L2 bans emoji).
  runPrimary: "Run",
  // Glossary "Run step: never task" wins over the handoff's "task" (L2; TASK-7521 log).
  reRunTask: "Re-run this step",
  reRunGroup: "Re-run group",
  retry: "Retry",
  reconnect: "Reconnect",
  viewRun: "View run",
  runningPill: "Running workbook agent",
  notStarted: "Not started",
  completeTitle: "Workbook agent completed",
  completeSub: "10 of 10 steps · 11 open items raised · finished Sep 10, 4:12 PM",
  completeProgress: "10 of 10 complete",
  completeStarted: "Started Sep 10, 3:31 PM",
  runningTitle: "Workbook agent is running",
  runningSub: "3 steps running at once.",
  runningProgress: "7 of 10 complete",
  runningStarted: "Started 2 minutes ago",
  idleTitle: "Workbook agent",
  idleSub:
    "Ready to run 10 steps · sources: QuickBooks Online, 2025 Binder (19 documents), 2024 Form 1065",
  waiting: "Waiting on 1 answer",
  failedTitle: "Stopped at Import trial balance",
  failedBody: "QuickBooks Online token expired — reconnect in Workbench › Connect",
  runningCapital:
    "Running… adding tax-exempt interest 6,200 as other increases (05 Capital!H8:H12)",
  runningK1: "Running… re-deriving Item L",
} as const;

export interface TaskCopy {
  key: string;
  name: string;
  meta: string;
  open: number;
}

export interface GroupCopy {
  key: string;
  title: string;
  tasks: readonly TaskCopy[];
}

/** The six task groups and ten rows of Run 2 (1 + 1 + 2 + 4 + 1 + 2 = 11 open items). */
export const GROUPS: readonly GroupCopy[] = [
  {
    key: "import",
    title: "Import trial balance",
    tasks: [
      {
        key: "import_trial_balance",
        name: "QuickBooks Online — Ridgeline Property Partners, LP",
        meta: "27 accounts · UTB balanced · AJE-1 18,500 approved by Samuel Ito · 1 open",
        open: 1,
      },
    ],
  },
  {
    key: "map",
    title: "Map to Form 1065 lines",
    tasks: [
      {
        key: "map_lines",
        name: "Line mapping — Form 8825, Schedule K, Schedule L",
        meta: "27 of 27 mapped · Unmapped 0 · TJE-1 6,200 to Schedule K line 18a · 1 open",
        open: 1,
      },
    ],
  },
  {
    key: "fixed_assets",
    title: "Fixed assets & depreciation",
    tasks: [
      {
        key: "depreciation_register",
        name: "Depreciation register — 6 assets + land",
        meta: "2025 depreciation 733,500 · 1 open",
        open: 1,
      },
      {
        key: "bonus_eligibility",
        name: "Bonus eligibility by acquisition date",
        meta: "100% bonus on 244,000 acquired after Jan 19, 2025 · 1 open",
        open: 1,
      },
    ],
  },
  {
    key: "capital",
    title: "Partner transactions & capital",
    tasks: [
      {
        key: "contributions_distributions",
        name: "Contributions & distributions",
        meta: "Contribution 250,000 (Jonah Feld) · distribution 600,000 on Dec 15 · No issues",
        open: 0,
      },
      {
        key: INTERIM_706D,
        name: "§706(d) interim closing — Pell Street transfer 6/30/2025",
        meta: "331,405 of capital moved · §743(b) placeholder 28,595 · 3 open",
        open: 3,
      },
      {
        key: CAPITAL_M2,
        name: "Capital accounts & Schedule M-2",
        meta: "Item L derives · M-2 off 6,200 · 1 open",
        open: 1,
      },
    ],
  },
  {
    key: "states",
    title: "States & PTET",
    tasks: [
      {
        key: "apportionment_ptet",
        name: "Apportionment & PTET — IL · CO · NY",
        meta: "IL 46.0% · CO 31.5% · NY 22.5% · PTET 64,096 · 1 open",
        open: 1,
      },
    ],
  },
  {
    key: "k1s",
    title: "Draft K-1s",
    tasks: [
      {
        key: FEDERAL_K1S,
        name: "Federal K-1s (5)",
        meta: "Σ K-1s = Schedule K · drafts shared with the Feld and Shah 1040s · 1 open",
        open: 1,
      },
      {
        key: STATE_K1S_K3S,
        name: "State K-1s & K-3s",
        meta: "IL · CO · NY state K-1s · K-3 for all 5 partners · 1 open",
        open: 1,
      },
    ],
  },
];

/** D: the §706(d) convention question (options from Reg. §1.706-4; Monthly recommended). */
export const QUESTION_706D = {
  question_id: "q-706d-convention",
  n: 1,
  m: 1,
  steps: [
    {
      q: "How should items be allocated around the 6/30/2025 Pell Street transfer?",
      preselect: "monthly",
      options: [
        {
          key: "monthly",
          title: "Interim closing, monthly convention",
          detail: "Matches the assignment agreement's 6/30 closing of the books · Recommended",
        },
        { key: "semi_monthly", title: "Interim closing, semi-monthly convention" },
        {
          key: "proration",
          title: "Proration (calendar-day convention)",
          detail: "Reg. §1.706-4: the proration method uses only the calendar-day convention",
        },
      ],
    },
  ],
  skipText: "Skip",
};
