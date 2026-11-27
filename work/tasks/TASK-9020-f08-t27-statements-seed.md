---
id: TASK-9020
title: "F-08-T27: Seed slice: Granite Peak FY2026 statements (TPL-22)"
spec: SPEC-000
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: green
status: in-review
branch: s54-f08-t27-statements-seed
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-27
updated: 2026-11-27
plan_key: F-08-T27
---

## Objective
Backlog row acceptance: "Seed tests foot the balance sheets to 26,410,000 and the lineage 11,906,000 - 486,000 = 11,420,000, and Note 9 reads through October 27, 2026."

## Done
- apps/web/src/fixtures/contracts/statements.ts: draft view-model types for T20 (line sources tb_linked / formula / override, pages, TOC, tie-out runs, presence, comments, Note 9, share) until R-01's contract deletes them
- seed/granite-peak-fy2026-statements.ts: the TPL-22 handoff's balance sheets (totals as formulas over other lines), Inventory's two TB groups, used-in rows, roll-forward times, tie-out runs #1 9:13 and #2 10:26, Simone's 10:24 relink 3,200,000 to 2,600,000, presence, the page-6 thread, Note 9 and the client share; 13 pages with only the handoff's placed pages listed (no invented page numbers)
- seed/granite-peak-fy2026-statements.foot.test.ts (8): both years foot by formula, lineage, cash-flow change 2,240,000, stale totals 16,110,000 / 27,010,000 and the relink restoring 26,410,000, run #2 214 of 214, Note 9 on page 13 of 13, presence, $ only on first and double-ruled lines

## Progress log
- `2026-11-27` — Built; 8 seed tests pass. DEC-6025.
