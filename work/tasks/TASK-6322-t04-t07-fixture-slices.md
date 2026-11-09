---
id: TASK-6322
title: T-04-T07 fixture slices and handlers for the return workspace
spec: SPEC-649
acceptance_criteria: [AC-1]
risk_zone: green
status: in-progress
epic: T-04
plan_key: T-04-T07
branch: s32-t04-t07
worktree: /Users/ayushkbhatia/Accrued/abacus-s32
created: 2026-11-09
updated: 2026-11-09
---

## Objective
The Feld return workspace on E0 for RW-1/WS-1 in fixture mode, with its footing test.

## Progress log
- `2026-11-09` — `fixtures/seed/tax-workspace.ts`, `fixtures/handlers/tax-workspace.ts`, foot test.
  Not run (end pass). Partial: the slice covers TAX-04 a/b/c/e, TXI-02 a and TXI-03 a/b; the
  per-screen `screens/<ID>/scenarios.ts` for all 50 artboards, the Feld document pages with region
  fixtures and the other states land with each screen's FE row (T-04's S33+ rows); the shapes
  switch to the generated client after `make generate`.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-3022 | Local shapes until generate; slice scope; writes 501 in fixtures as live | no |
- `2026-11-09` — S32 end pass: gates, unit, contract, S32 integration and web suites run; fixes folded into the end-pass PR. Status partial.
- `2026-11-09` — Partials round (branch s32p-t04-t07, DEC-3031): fixtures typed with the generated
  client; RW-1's two derived-status fields typed as Literals (they were empty enums); C2 guard test
  against empty enums. Still open: per-screen scenarios with each screen's FE row.
