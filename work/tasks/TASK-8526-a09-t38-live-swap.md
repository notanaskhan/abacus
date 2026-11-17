---
id: TASK-8526
title: "A-09-T38: Fixture-to-live swap: AUD-34 group scoping and AUD-33's elimination proposer"
spec: SPEC-658
acceptance_criteria: [AC-4, AC-5]
risk_zone: green
status: in-review
branch: a09-t38-live-swap
worktree: /Users/ayushkbhatia/Accrued/abacus-s49
created: 2026-11-17
updated: 2026-11-17
plan_key: A-09-T38
---

## Objective
Spec section: docs/plan/epics/A-09.md §5. Fixture-to-live swap for AUD-31 group, AUD-32 to AUD-35 and POR-23 on the generated client: 409 and 422 refusals in plain words, polling for pull-all and mapping runs, Undo toasts, capability-off fallbacks.

## Plan (green)
1. AUD-34: a view model (`Aud34Data`) fed by the fixture (FIXTURE_DATA) or the live read (`GroupScopingLive` over `groupScopingOptions`; `liveData` formats the server's figures, no arithmetic); a 404 falls back to the flag-off state.
2. AUD-33: 'Propose with the agent' in the eliminations drawer (unlocked, nothing proposed) over A-09-T34's live route; 409 capability_unavailable reads in plain words.
3. Tests: `screens/AUD-34/live.test.ts`; AUD-33 and AUD-34 suites green.

## Progress log
- `2026-11-17` — Built in the S49 sequential stack. tsc and eslint clean; AUD-33/AUD-34 22 tests and the live mapping test pass. Partial: AUD-31, AUD-32, AUD-33 and POR-23 were already live (A-09-T32/T33, S48); AUD-35's queue stays on fixtures (its live service routes are A-09-T27's but the screen's tracker needs a view-model refactor like AUD-34's); 'on staging' cannot be checked (no staging environment, S25 note). Gates and tests run once at the S49 end pass (build first, test last).
