---
id: TASK-2325
title: T-02-T17 duplicate-upload policy (red, evidence)
spec: SPEC-502
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: red
status: in-review
epic: T-02
plan_key: T-02-T17
branch: s18-t02-t17
worktree: /Users/ayushkbhatia/Accrued/abacus-s18
created: 2026-10-30
updated: 2026-10-30
---

## Objective
Client-channel same-hash uploads accepted and flagged under `evidence.duplicate_review`; Keep newer
or Discard duplicate through P-31's void path; firm uploads keep the 409; an accepted version is
never discarded.

## Plan
- Migration 0468 `duplicate_resolutions`; `evidence/duplicates.py`; `uploads.attach/upload`;
  `evidence/duplicates_contract.py` route; registry, schema_check, route pins; DEC-1371.
- Tests: `tests/unit/evidence/test_t02t17_duplicates.py` (7); integration in the end review.

## Progress log
- `2026-10-30` — built (DEC-1371). `tests/unit/api/test_app_gates.py::test_ac20` fails on main
  already (report-template routes missing from its list); not this change. `[skip ci]`.

## Handoff
- **Current state:** built, PR open, held for the S18 batch.
- **Exact next step:** F-06-T15.
