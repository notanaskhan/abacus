---
id: TASK-8762
title: "Q-03-T352: ADR-078 catch-up lane 2028 Q3: independent AC suites for the red and amber work an epic deferred under its cut list (A-08, A-09, W-01, C-01) (part 2 of 3)"
spec: SPEC-000
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: red
status: in-review
branch: s51-q03t352
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-20
updated: 2026-11-20
plan_key: Q-03-T352
---

## Objective
No red or amber task of the period reaches its gate without an AC suite by you.

## Plan (red)
1. Map every red and amber build row of A-08, A-09, W-01 and C-01 to the ADR-078 suite that covers it, from the suites' row titles.
2. Run the 19 ADR-078 and contract suites once.
3. Write suites for the rows nothing covered: C-01-T09, C-01-T11, W-01-T04, A-09-T12 (schema rules), from each row's acceptance and the migration's stated contract, read from the Postgres catalogue.
4. Record the lane in `docs/plan/status/S51-adr078-lane.md`.
5. Rollback: revert the PR (tests and docs only).

## Progress log
- `2026-11-20` — 19 suites: 356 passed, 1 xfailed. New `tests/integration/test_q03t352_catchup_independent.py`: 41 pass; ruff and pyright clean. Before commit one assertion of mine failed (the app holds DELETE on integration_oauth_states); it is not in W-01-T04's contract, so it was dropped and logged in the lane note rather than reported as a defect. Not done: row-level behavioural checks of the freeze and the A-09-T12 refusals, up/down/up on staging copies, and a separate seeded-vulnerable-build run. Gates and tests run once at the S51 end pass (build first, test last).
