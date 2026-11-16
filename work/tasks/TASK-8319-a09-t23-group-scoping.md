---
id: TASK-8319
title: "A-09-T23: Group scoping compute and service in assurance"
spec: SPEC-658
acceptance_criteria: [AC-5]
risk_zone: amber
status: in-review
branch: a09-t23-group-scoping
worktree: /Users/ayushkbhatia/Accrued/abacus-s47g04
created: 2026-11-16
updated: 2026-11-16
plan_key: A-09-T23
---

## Objective
Spec section: docs/specs/SPEC-658 F5.
Group scoping compute and service in assurance.

## Plan (amber)
1. `assurance/compute/group_scoping.py` (pure): thresholds from the chosen group materiality (PM 75%, CT 5%), the firm-standard component PM default, the component PM rule (below group PM, else 422), coverage from contributions after eliminations (covered unless analytics only; whole percents half up), aggregation facts.
2. Tests: `tests/unit/assurance/test_a09t23_group_scoping.py`.

## Progress log
- `2026-11-16` — Built in the S47 sequential stack (DEC-5315). The unit file ran green (3 tests: 240,000 / 180,000 / 12,000; 78% and 22% of 50,760,000; 180,000 answers the rule). Partial: the AUD-34 service and routes (components PUT, the `group_materiality` and `make_reference` decision kinds reserved to the EP with rationale and fresh MFA, Remind, the recommender mode hook) and the options from A-04's engine are not wired. Gates and
  tests run once at the S47 end pass (build first, test last).
