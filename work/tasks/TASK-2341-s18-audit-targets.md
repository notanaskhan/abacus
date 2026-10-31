---
id: TASK-2341
title: S18 audit target types placed; T-01-T19 test wires its own storage
spec: SPEC-501
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: green
status: in-review
epic: T-01
plan_key: S18-ci
branch: s18-ci-fixes2
worktree: /Users/ayushkbhatia/Accrued/abacus-s18
created: 2026-10-31
updated: 2026-10-31
---

## Objective
Fix the rest of main's CI failures that S18's work caused (seen on #933's run): audit target types
S18 records but the audit trail could not place, and T-01-T19's engine-import test answering 500
in CI. Other sessions' failures stay with them (DEC-1387).

## Plan
- `audit_trail/targets.py`: `reference_set_version` (K-02-T12), `questionnaire_template`
  (T-02-T16) and `consent_export` (T-01-T16) are firm-level.
- `requests/audit_targets.py`: `question` placed on its questionnaire's engagement.
- `organisations/audit_targets.py` (new), registered from `organisations/api.py`: `consent` placed
  on its client.
- `tests/integration/test_t01t19_engine_import.py`: configures evidence storage against the S3
  test container; without it the upload reached the default endpoint (CI:
  `EndpointConnectionError`, 500).

## Progress log
- `2026-10-31` — built; ruff, pyright, lint-imports, banned patterns clean on the files; T-01-T19
  passes; `test_targets` lists only other sessions' kinds. `[skip ci]` on commits; the merge runs
  CI.

## Handoff
- **Current state:** PR open.
- **Exact next step:** merge with CI.
