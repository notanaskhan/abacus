// F-08-T02 (DEC-5617): Granite Peak FY2026 audit programs on the board (TPL-21a at Thu Sep 24,
// 2026, 9:30 AM CT). Every card is the TPL-21 handoff row (title, ref, owner, metrics, state);
// columns are read from its sign-off slots (P and R signed: Complete; P only: In review). The
// Planning lane is collapsed "8 of 8 ✓" and holds no card here. Footings are tests.
import type { BoardCardDraft, BoardDraft } from "../contracts/board";

type Card = [
  string,
  string,
  "CH" | "SB",
  BoardCardDraft["column"],
  [number, number, number, number],
  string | null,
  string | null,
  BoardCardDraft["overlay"]?,
];
const CARDS: Card[] = [
  ["BH-FS-310", "Cash & Bank Confirmations", "CH", "complete", [2, 6, 1, 0], "CH", "HL"],
  ["BH-FS-320", "Sampling — Accounts Receivable", "SB", "in_review", [1, 14, 1, 0], "SB", null],
  ["BH-FS-325", "Confirmations", "CH", "in_progress", [6, 2, 0, 1], null, null],
  [
    "BH-FS-330",
    "Tests of Details — Revenue & AR",
    "SB",
    "in_progress",
    [2, 9, 1, 0],
    null,
    null,
    "needs_input",
  ],
  ["BH-FS-340", "Inventory Observation", "CH", "complete", [5, 8, 0, 0], "CH", "HL"],
  ["BH-FS-350", "PP&E & Depreciation", "CH", "in_review", [1, 7, 1, 0], "CH", null],
  ["BH-FS-410", "Accounts Payable", "CH", "not_started", [10, 0, 0, 0], null, null],
  ["BH-FS-420", "Accrued Liabilities", "CH", "not_started", [10, 0, 0, 0], null, null],
  [
    "BH-FS-430",
    "Search for Unrecorded Liabilities",
    "CH",
    "not_started",
    [10, 0, 0, 0],
    null,
    null,
  ],
  [
    "BH-FS-440",
    "Revolver & Term Loan",
    "SB",
    "in_progress",
    [3, 4, 1, 0],
    null,
    null,
    "waiting_on_client",
  ],
  ["BH-FS-460", "Equity", "SB", "not_started", [10, 0, 0, 0], null, null],
  [
    "BH-FS-510",
    "Journal Entry Testing",
    "SB",
    "in_progress",
    [3, 1, 0, 0],
    null,
    null,
    "agent_running",
  ],
  ["BH-FS-520", "Estimates & Related Parties", "SB", "in_progress", [2, 3, 1, 0], null, null],
];

// F-08-T23: each program's audit area (its lane) and C-26 state, as TPL-21 lists them.
const AREA: Record<string, string> = {
  "BH-FS-310": "cash",
  "BH-FS-320": "receivables",
  "BH-FS-325": "receivables",
  "BH-FS-330": "receivables",
  "BH-FS-340": "inventory",
  "BH-FS-350": "property",
  "BH-FS-410": "payables",
  "BH-FS-420": "payables",
  "BH-FS-430": "payables",
  "BH-FS-440": "debt",
  "BH-FS-460": "debt",
  "BH-FS-510": "journal",
  "BH-FS-520": "estimates",
};
const AGENT: Record<string, BoardCardDraft["agent"]> = {
  "BH-FS-310": "done",
  "BH-FS-320": "done",
  "BH-FS-325": { pct: 50 },
  "BH-FS-330": { pct: 60 },
  "BH-FS-340": "done",
  "BH-FS-350": "done",
  "BH-FS-410": "not_run",
  "BH-FS-420": "not_run",
  "BH-FS-430": "not_run",
  "BH-FS-440": { pct: 70 },
  "BH-FS-460": "not_run",
  "BH-FS-510": { pct: 35, running: true },
  "BH-FS-520": { pct: 50 },
};

export const AUDIT_PROGRAM_BOARD = {
  engagement: "Granite Peak Outdoor Co. · FY2026 audit",
  cards: CARDS.map(
    ([ref, title, owner, column, [days, evidence, requests, todos], p, r, overlay]) => ({
      ref,
      title,
      owner,
      column,
      metrics: { days, evidence, requests, todos },
      ...(overlay === undefined ? {} : { overlay }),
      signoffs: { preparer: p, reviewer: r },
      ...(AREA[ref] === undefined ? {} : { area: AREA[ref] }),
      ...(AGENT[ref] === undefined ? {} : { agent: AGENT[ref] }),
      ...(ref === "BH-FS-325" ? { sub: "2 of 4 responses" } : {}),
    }),
  ),
  binder: { preparer: 12, reviewer: 10, total: 21 },
  areas: [
    { key: "planning", title: "Planning", phase: "planning", programs: 8 },
    { key: "cash", title: "Cash", phase: "execution", programs: 1 },
    { key: "receivables", title: "Receivables & revenue", phase: "execution", programs: 3 },
    { key: "inventory", title: "Inventory & cost of sales", phase: "execution", programs: 1 },
    { key: "property", title: "Property", phase: "execution", programs: 1 },
    { key: "payables", title: "Payables & accrued", phase: "execution", programs: 3 },
    { key: "debt", title: "Debt & equity", phase: "execution", programs: 2 },
    { key: "journal", title: "Journal entries", phase: "execution", programs: 1 },
    { key: "estimates", title: "Estimates & related parties", phase: "execution", programs: 1 },
  ],
} satisfies BoardDraft;

/** TPL-21c: Cole drags BH-FS-430 to In progress; the run starts (0d · 0 · 1 · 0, 40%). */
export function afterBhFs430Move(board: BoardDraft): BoardDraft {
  return {
    ...board,
    cards: board.cards.map((c) =>
      c.ref === "BH-FS-430"
        ? {
            ...c,
            column: "in_progress",
            overlay: "agent_running",
            metrics: { days: 0, evidence: 0, requests: 1, todos: 0 },
            agent: { pct: 40, running: true },
          }
        : c,
    ),
  };
}
