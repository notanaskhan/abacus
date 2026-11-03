---
id: TASK-3236
title: Q-03-T171 ADR-078 catch-up lane 2027 Q4 (S26 amber rows)
spec: SPEC-000  # row
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
epic: Q-03
plan_key: Q-03-T171
branch: s26b-q03-t171
worktree: /Users/ayushkbhatia/Accrued/abacus-s26
created: 2026-11-03
updated: 2026-11-03
---

# TASK-3236 · Q-03-T171 · ADR-078 catch-up lane, 2027 Q4

## Built
`backend/tests/contracts/acceptance_independence/test_q03t171_s26_catch_up.py` (17 pass): independent declarations for the S26 amber rows without their own suite:
- A-04-T25: control writes refuse agent, system and clients; routing with no registered route is 503 `route_not_available`; an agent's severity is a suggestion by schema (0657 CHECKs).
- A-06-T13: `deficiency_severity` and `sum_conclusion` reserved to the engagement partner; concluding is human-only.
- A-06-T19: statement versions and parts insert-only; statement writes refuse clients and the agent.
- T-03-T02/T04: tax writes refuse clients and the agent; the payments engine never uses float, rounds half-up through the kernel and imports only `kernel.numeric` and `kernel.calendar`.

Already covered: A-04-T07/T18/T19 (A-04-T30), A-05 (A-05-T25, T29), adjustments (A-06-T17), notices (N-04-T10), C4 v1.1 (P-11-T20). Acceptance: no S26 amber row reaches its gate without an AC suite.

## Partial
- Mutation-survivor tests are not added (the mutation floors run in their own lane).

## Progress log
- 2026-11-03: written and run (17 passed).
