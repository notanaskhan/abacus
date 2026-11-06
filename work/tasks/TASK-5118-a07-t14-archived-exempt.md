---
id: TASK-5118
title: A-07-T14 archived_exempt in the matrix, 409 archived and the system archive transition
spec: SPEC-000  # row (A-07-T14)
acceptance_criteria: [AC-1]
risk_zone: red
status: in-review
epic: A-07
plan_key: A-07-T14
branch: s29-a07-t14
worktree: /Users/ayushkbhatia/Accrued/abacus-s29
created: 2026-11-06
updated: 2026-11-06
---

## Objective
The API answers 409 archived whichever route reached a locked row; only declared actions act after lock; an engagement archives itself when its work items are.

## Plan
archived_exempt modifier in authz/matrix.py; assurance.yaml and evidence.yaml marks; AB409 handler in api/app.py; RowArchived in kernel/errors.py; engagements.archive_when_items_archived. Rollback: revert.

## Progress log
- 2026-11-06: built. `backend/tests/security/test_a07t14_archived_exempt.py` written, not run (end pass). Regenerated; pyright and banned patterns on touched files.

## Decisions made during this task
DEC-2414
