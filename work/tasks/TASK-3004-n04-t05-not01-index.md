---
id: TASK-3004
title: N-04-T05 NOT-01 a, e, f, g on the T1 IndexList in fixture mode
spec: SPEC-000  # row
acceptance_criteria: [AC-1]
risk_zone: green
status: in-review
epic: N-04
plan_key: N-04-T05
branch: s25-n04-t05 (stacked on s25-n04-t04)
worktree: /Users/ayushkbhatia/Accrued/abacus-s25
created: 2026-11-02
updated: 2026-11-02
---

## Objective
- **[AC-1]** NOT-01 a, e, f and g render in fixture mode on the notices v1 stub with tallies equal
  to the visible rows; only N4 is red; state rows read "Awaiting agency".

## Built
- `fixtures/seed/notices.ts`, `fixtures/handlers/notices.ts`, `fixtures/scenarios/NOT-01.ts`.
- `domain/notices/` (filters, `useNotices`, `useNoticesSummary`).
- `screens/NOT-01/` (index, copy, scenarios, test); `routes/firm/notices.tsx`; nav `routed`; manifest `fixture`.
- `packages/ui`: `IndexList.barEnd`, `IndexList.tilesAfter`, `GroupedTile`.

## Acceptance
| Check | Test |
|---|---|
| a order, tiles, type tile, summary, risk tints, amounts, authorizations | `screens/NOT-01/NOT-01.test.tsx` a cases |
| e New tile filter | e cases |
| f empty, g loading | f, g cases |

## Progress log
- 2026-11-02: built; tsc and eslint clean. Vitest at the S25 end review.

## Decisions made during this task
DEC-2054.
