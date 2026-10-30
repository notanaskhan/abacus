---
id: TASK-2324
title: T-02-T22 portal questionnaire routes
spec: SPEC-502
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: amber
status: in-review
epic: T-02
plan_key: T-02-T22
branch: s18-t02-t22
worktree: /Users/ayushkbhatia/Accrued/abacus-s18
created: 2026-10-30
updated: 2026-10-30
---

## Objective
POR-05's routes: list, get (filters, sections), autosave with If-Match and saved_at, mark-done,
addressee-only submit-and-lock. Attachments, notifications and the home to-do source per DEC-1370.

## Plan
- `requests/portal_questionnaires.py`; portal routes live; `engagements.api.contact_ids_of_user`.
- Tests: `tests/unit/requests/test_t02t22_portal_questionnaires.py` (13); contract stubs (33).
- Stacked on T-02-T16 (#852). DEC-1370.

## Progress log
- `2026-10-30` — built (DEC-1370). `[skip ci]`.

## Handoff
- **Current state:** built, PR open, held for the S18 batch.
- **Exact next step:** T-02-T17 duplicate-upload policy.
