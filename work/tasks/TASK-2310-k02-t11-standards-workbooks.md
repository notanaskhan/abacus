---
id: TASK-2310
title: K-02-T11 firm-standard content import and export
spec: SPEC-500
acceptance_criteria: [AC-45, AC-46, AC-47, AC-48]
risk_zone: amber
status: in-review
epic: K-02
plan_key: K-02-T11
branch: s18-k02-t11
worktree: /Users/ayushkbhatia/Accrued/abacus-s18
created: 2026-10-30
updated: 2026-10-30
---

## Objective
POST /v1/standards/{id}/imports (XLSX or CSV to a Draft with problems), POST /v1/standards/imports
bulk onboarding, GET export.xlsx; an import never publishes. Acceptance (row): exporting 1065
Review Checklist v4 and importing the file again produces a draft with an empty diff, and no
import changes a published version.

## Plan
- `methodology/standards_import.py` (format, export, read, onboarding); `standards.import_draft`
  and `version_payload`; routes in `standards_routes.py` (raw body, DEC-1357);
  `identity.api.emails_of`; error catalogue and `make generate`.
- Tests: `tests/unit/methodology/test_k02t11_standards_workbooks.py`.
- Rollback: revert.

## Progress log
- `2026-10-30` — built (DEC-1357). Tests written, not yet run (S18 end review; `[skip ci]`).

## Handoff
- **Current state:** built, PR open, held for the S18 batch.
- **Exact next step:** K-02-T12 publication fan-out (on K-02-T06).
