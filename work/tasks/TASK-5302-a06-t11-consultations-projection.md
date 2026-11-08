---
id: TASK-5302
title: A-06-T11 consultations, projected conversion, one unit of work
spec: SPEC-000  # row
acceptance_criteria: [AC-1]  # the row's atomic record, projection from sampling and minimal consultations
risk_zone: amber
status: done
epic: A-06
plan_key: A-06-T11
branch: s25-a06-t11-findings
worktree: /Users/ayushkbhatia/Accrued/abacus-s25
created: 2026-11-06
updated: 2026-11-06
---

## Objective
Close what DEC-2063 left of A-06-T11.

## Plan (amber)
- `review.api.create_issue_in`: the issue in the caller's unit of work; `record_finding` uses it.
- `findings.to_misstatement`: projected takes the sample error and `projection_ref`; the figure comes
  from `sampling.api`; evaluation rows on the finding, inputs in the misstatement's `projection`.
- `assurance/consultations.py` and three routes; matrix `consultation.conclude`, `consultation.read`
  widened; `make regenerate`, `make generate`; audit names reviewed.
- Tests: `tests/integration/backfill/test_a06t11_consultations_projection.py`,
  `tests/unit/assurance/test_a06t11_findings.py`, `tests/contracts/a06_completion/`.
- Rollback: revert. No migration; 0644's tables are unchanged.

## Progress log
- 2026-11-06: built. The sample set's view is stubbed at `sampling.api` in the integration test,
  so a live approved set through the conversion is not exercised here.

## Decisions made during this task
DEC-2485.
