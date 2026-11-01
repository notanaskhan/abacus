---
id: TASK-2905
title: A-04-T17 golden fixtures and independent acceptance tests for the materiality engine and service
spec: SPEC-620
acceptance_criteria: [A-04 §3.3, §3.9]
risk_zone: amber
status: in-review
epic: A-04
plan_key: A-04-T17
branch: s24-a04-t17 (stacked on s24-a04-t12)
worktree: /Users/ayushkbhatia/Accrued/abacus-s24
created: 2026-11-01
updated: 2026-11-01
---

## Objective

Golden fixtures pinning every figure in A-04 §3.3 with exact Decimal equality, independent tests of the service's human-only decide, and the CPA review request of materiality@1.

## Acceptance (backlog)

The goldens assert exact Decimal equality for every figure in section 3.3, and the CPA review of materiality@1 is requested with the case list hash.

## Plan

- `backend/tests/golden/materiality/{northwind_py2025,granite_peak_fy2026}.yaml` (transcribed from the plan) and `test_a04t17_materiality_goldens.py` (benchmarks and ranges, options with PM and CT, v2, v3's final basis, prior years and growth, the case list hash named by the memo).
- `docs/quality/golden-reviews/materiality@1.md`: the CPA memo with the case list hash `a8332215…b678`, review requested.
- `tests/integration/backfill/test_a04t17_materiality_independent.py`: the matrix denies decide to the agent and the system; the database's CHECK refuses an agent, system or support decision; no fresh second factor 403 `mfa_required`; a blank rationale 422; a new proposal after a decision is v3 with v2 standing; a rate outside the range 409 with no card; staff read but never propose.
- The engine's property tests are A-04-T08's on main (`tests/property/assurance/test_a04t08_materiality_properties.py`).

## Progress log

- 2026-11-01: written in abacus-s24, stacked on A-04-T12. The case list hash was computed once to write the memo; the tests are not run.
- Human to-do: the audit CPA signs `docs/quality/golden-reviews/materiality@1.md`.
