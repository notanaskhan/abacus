---
id: TASK-6571
title: "T-04-T13 remainder: TAX-04's demo lights in the handoff's order and the poster holds all four"
spec: SPEC-649  # T-04 TAX-04
acceptance_criteria: [AC-1]  # the row's acceptance (Objective)
risk_zone: green
status: in-review
branch: s33t-t04-t13-poster
worktree: /Users/ayushkbhatia/Accrued/abacus-s33
created: 2026-11-10
updated: 2026-11-10
plan_key: T-04-T13
---

## Objective
Handoff TAX-04 MOTION: box 1a lights at 700 ms, box 1b at 1000, line 3b at 1950 and line 3a at
2250; the 3600 ms poster holds all four. The MatchStore lit one match at a time, so the demo drew
1a with 3b together at 700 ms.

## Build
- `@abacus/ui` MatchStore: `keepLit(id, kind)` keeps one element kind of a match lit beside the
  match (`MatchState.kept`, optional; `keptKey`); any other move (intent landing, pin, light,
  clear, Escape) emits a state without it, so the still frame goes when a person moves the match.
  `useMatch` reads it by the element's own kind. Additive: no consumer changes.
- `screens/TAX-04/index.tsx`: the four steps on the handoff's timings (regions for the boxes, rows
  for the lines); reduced motion keeps all four at once.
- Tests: `TAX-04.test.tsx` (the order and the poster), `packages/ui/src/tracing/tracing.test.tsx`.

## Progress log
- `2026-11-10` — Built; TAX-04 (15) and tracing (24) tests pass. Gates at the end of the round.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-3171 | A still frame is kept per element kind beside the match; a person's move lets it go | no |
