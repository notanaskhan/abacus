---
id: TASK-7722
title: P-02-T12 Playwright palette spec and J13 4, J16 5 and 9
plan_key: P-02-T12
spec: SPEC-000  # docs/screens/SHL-02.md; C15 v1
acceptance_criteria: [AC-1]  # shl-02-palette.spec.ts, J13 4, J16 5 and 9 with axe and INV-1/3/4 on every state
risk_zone: green
status: in-review
branch: p02-t12-palette-e2e
worktree: /Users/ayushkbhatia/Accrued/abacus-s41
created: 2026-11-13
updated: 2026-11-13
---

## Objective
`shl-02-palette.spec.ts` (fixture and full stack), J13 step 4 (TXP-01 landing `test.fixme` until
T-05), J16 steps 5 and 9, with `assertInvariants` (INV-1, INV-3, INV-4) and axe on every state.

## Plan
- `apps/web/e2e/screens/shl-02-palette.spec.ts` (new); J13 and J16 journey files (appended).
- `src/fixtures/seed/shl02.ts` (`SHL02_RIDGELINE`), `src/fixtures/screen-scenarios.ts` (+ test list).
- Rollback: revert.

## Partial
- Full stack and staging need `search.palette` on for the firm (P-02-T14 rollout); until then
  those projects' palette steps fail on a closed palette, the reason T14 turns the flag on.
- `shl-02 g` is `test.fixme` (W-03 saved prompts); `shl-02 c` fixture-only (agent mode, W-02).
- The context-bound actions of P-02-T10's rest (held #1858) are not asserted here.

## Progress log
- 2026-11-13: built; eslint and tsc clean; specs written, not run.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-4725 | real shell on scenarios; existing journey files; ridgeline fixture | no |
