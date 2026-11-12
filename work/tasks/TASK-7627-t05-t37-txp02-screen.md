---
id: TASK-7627
title: T-05-T37 TXP-02 Review › Financials (TB → TTB) screen
plan_key: T-05-T37
spec: SPEC-651
acceptance_criteria: [AC-F3]  # nine artboards render; every column foots on screen; keyboard reaches the picker
risk_zone: green
status: in-review
branch: t05-t37-txp02-screen
worktree: /Users/ayushkbhatia/Accrued/abacus-s40
created: 2026-11-12
updated: 2026-11-12
---

## Objective
TXP-02 on the entity return's Review › Financials tab: control bar, tally strip and the TB pane in
the TB grammar, from the server's figures.

## Plan
- Backend (additive contract): `entity_tb.group_of`, `totals`, `figures`; row `adjusted`,
  `prior_year`, `group`; `WorkbookTbTotalOut`, `WorkbookFigureOut`. Test
  `backend/tests/unit/tax/test_t05t37_tb_sections.py`. Client regenerated (`make generate`).
- `packages/ui/src/format.ts`: `dollars` amount style; test `format.dollars.test.ts`.
- `apps/web/src/screens/TXP-02/{copy.ts,index.tsx,Financials.tsx,TXP02.test.tsx}`;
  `screens/TXP-00/EntityReturn.tsx` dispatches `review/financials`.
- Fixtures: `seed/tax-entity.ts` gains PY, ATB, sections, totals, statements, line view and
  tallies (verbatim from the handoff); `handlers/tax-entity.ts` serves statement, filter, tallies.
- Manifest TXP-02 `fixture` at `/tax-returns/$returnId/review/financials`; screen contract notes.

## Partial
- a2, a3, e2 overlays (SHL-09, AJE drawer, line picker) are raised as callbacks; wired with
  T-05-T38's SHL work.
- Three of nine tally cards (Balance Sheet, Capital Tie, Retained Earnings) need server tallies.
- PY is null live until the prior-year TB import; view/statement are component state.

## Progress log
- `2026-11-12` — Screen, fixtures and contract additions built (DEC-4622). Tests at the end pass.
