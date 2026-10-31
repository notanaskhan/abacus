---
id: TASK-2606
title: P-11-T15 independent AC tests for template import and publication
spec: SPEC-520
acceptance_criteria: [AC-1, AC-2, AC-3, AC-4]
risk_zone: amber
status: in-review
epic: P-11
plan_key: P-11-T15
branch: s21-p11-t15
worktree: /Users/ayushkbhatia/Accrued/abacus-s21
created: 2026-10-31
updated: 2026-10-31
---

## Objective
ADR-078's independent suite for P-11-T06, written from SPEC-520 AC-1 to AC-4 and the row's
acceptance: "An agent or worker context never publishes, a published version never changes, and
every publication names a person."

## Scope
**In**: `backend/tests/integration/test_p11t15_template_publication_acs.py` (Postgres, through
C11's service layer as the routes call it); the defects it found in
`methodology/report_templates.py` (DEC-1656).
**Out**: the renderer suite (P-11-T14); the content scan (AC-5, already in P-11-T06's unit suite).

## Plan
1. [x] Tests from the spec: dry-run report by path and nothing stored; unknown block refused by the
   closed union; markup, CSS, URL and expression variants refused; an import is an insert-only
   draft audited naming the importer; practice leader or quality partner publishes with a fresh
   second factor; stale or missing factor, agent, system, support, firm admin, manager, staff, a
   client principal, another firm and the importer never publish; a correction is a new version;
   the same content stores nothing; republishing rolls back; 409 `already_published`; no role
   updates or deletes a version or a publication; every publication row and audit event names a
   person and their second factor.
2. [x] Fix what the suite found (DEC-1656). Rollback: revert the PR (no migration).

## Progress log
- `2026-10-31` — Suite written from the spec; first run against Postgres failed every import:
  three P-11-T06 defects (DEC-1656), fixed; 40 passed, P-11-T06's own suites still green (72).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-1656 | Template import and publication fixed from P-11-T15's independent suite | No |
