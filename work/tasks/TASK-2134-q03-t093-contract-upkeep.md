---
id: TASK-2134
title: Q-03-T093 Contract-test upkeep 2027 Q2 (N-provided contracts)
spec: SPEC-000  # Q-03-T093 row; docs/contracts/README.md
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: amber
status: in-review
epic: Q-03
plan_key: Q-03-T093
branch: s16-q03-t093
created: 2026-10-29
updated: 2026-10-29
---

## Objective
Consumer suites green in provider CI, fixture-versus-live drift tickets, openapi-compat
exceptions and vN+1 overlap retirements.

Acceptance (backlog row): "Every consumer suite is green in provider CI and the drift count is
zero at the quarter's end."

## Progress log
- 2026-10-29: `python -m abacus_tools.contracts --check` passes on main (12 frozen snapshots).
  No contract holds two versions, so no vN overlap is due for retirement. Fixture-versus-live
  drift: 1 route, `PUT /v1/engagements/{id}/auto-mode` (ED-270, owner P-10-T39, S36). Not stubbed
  here: a stub would add the `engagement_run.auto_mode` matrix action, `/v1/me` would report the
  capability and AUD-02's switch would render live against a 501. It stays the one known drift,
  allowed by name in `route-drift.test.ts` until P-10-T39. The consumer suites (`pytest
  tests/contracts`) run at the S16 end review.
