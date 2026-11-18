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
    }),
  ),
  binder: { preparer: 12, reviewer: 10, total: 21 },
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
          }
        : c,
    ),
  };
}
