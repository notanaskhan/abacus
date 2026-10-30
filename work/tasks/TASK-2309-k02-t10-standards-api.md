---
id: TASK-2309
title: K-02-T10 deterministic standards API
spec: SPEC-500
acceptance_criteria: [AC-39, AC-40, AC-41, AC-42, AC-43, AC-44]
risk_zone: amber
status: in-review
epic: K-02
plan_key: K-02-T10
branch: s18-k02-t10
worktree: /Users/ayushkbhatia/Accrued/abacus-s18
created: 2026-10-30
updated: 2026-10-30
---

## Objective
classify_entry (attest clients always held), variance_exceeded (percent AND amount),
materiality_range_for and validate_materiality, confidence_hold, required_review_levels,
return_approval_policy, ssars_framework_for; every result names its policy version; Hypothesis
properties.

## Plan
- Replace the K-02-T08 stubs in `methodology/standards_contract.py` (already exported through
  `methodology.api`); `StandardRowMissing` (422); error catalogue regenerated.
- Tests: `tests/unit/methodology/test_k02t10_standards_api.py` (examples + Hypothesis).
- Rollback: revert.

## Progress log
- `2026-10-30` — built (DEC-1356). Tests written, not yet run (S18 end review; `[skip ci]`).

## Handoff
- **Current state:** built, PR open, held for the S18 batch.
- **Exact next step:** K-02-T11 import/export; T-01-T18 consumes these.
