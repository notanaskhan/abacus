---
id: TASK-9016
title: "T-08-T21: Filing-deadline exports and the T-7 / T-1 notice sweep"
spec: SPEC-710
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: amber
status: in-review
branch: s54-t08-t21-deadline-alerts
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-27
updated: 2026-11-27
plan_key: T-08-T21
---

## Objective
Backlog row acceptance: "Exports re-render byte-identical and carry no TIN or amount, and each deadline yields at most one notice per threshold." The xlsx and ics exports (T-08-T10) existed; this row adds the filing_deadline.approaching sweep and fixes the export's permission.

## Done
- practice/deadline_alerts.py: sweep(tenant_id, today=) after each firm's nightly recompute; open deadlines within 7 days reach t_minus_7 or t_minus_1, written once per (deadline, threshold, due date) to filing_deadline_alerts (0962), one audit event and one notice each, to owners and signer less walled people
- A deadline first seen inside a day is told once at t_minus_1 (t_minus_7 written as passed); overdue and done never told; a moved due date may be told again
- New matrix action filing_deadline.export (firm roles, fresh MFA, not offshore, people only): export.create is an engagement action and granted no one on the firm-scope calendar (a T-08-T10 defect found by running the export on Postgres)
- Tests: tests/integration/test_t08t21_deadline_alerts.py (4, Postgres) and tests/unit/practice/test_t08t21_thresholds.py
- Contract docs/contracts/filing-deadlines.md section added; DEC-6022

## Progress log
- `2026-11-27` — Built and passing on Postgres with the security generated suites (15,379 passed). No migration: 0962's filing_deadline_alerts was made for this.
