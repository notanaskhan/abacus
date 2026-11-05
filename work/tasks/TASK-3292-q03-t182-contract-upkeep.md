---
id: TASK-3292
title: Q-03-T182 Contract-test upkeep 2027 Q4 (N-provided contracts)
spec: SPEC-000  # Q-03-T182 row; docs/quality/sweeps/2026-11-05-q03-t182-contract-upkeep.md
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: amber
status: in-review
epic: Q-03
plan_key: Q-03-T182
branch: s27-q-03-t182
created: 2026-11-05
updated: 2026-11-05
---

## Objective
Consumer suites green in provider CI, fixture-versus-live drift tickets from the nightly report,
openapi-compat exceptions and vN+1 overlap retirements.

Acceptance (backlog row): "Every consumer suite is green in provider CI and the drift count is zero at the quarter's end."

## Progress log
- 2026-11-05: `abacus_tools.contracts --check` passes. Main's CI had 5 contract failures from S27, fixed
  in #1222. Drift is 1 known route (ED-270), so the row's zero is not met.

## Open (not met here)
- Drift count is 1, not 0, until P-10-T39 (S36).
- Provider CI has not re-run with #1222 merged.
