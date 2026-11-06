---
id: TASK-5117
title: "A-07-T13 archived_guard: DB immutability after lock, with ARCHIVE-001"
spec: SPEC-000  # row (A-07-T13)
acceptance_criteria: [AC-1]
risk_zone: red
status: in-review
epic: A-07
plan_key: A-07-T13
branch: s29-a07-t13
worktree: /Users/ayushkbhatia/Accrued/abacus-s29
created: 2026-11-06
updated: 2026-11-06
---

## Objective
On a locked work item every write to a guarded table raises archived; the only way past is a reviewed kind set by an allowlisted service.

## Plan
Migration 0686; kernel/db/archive_guard.py (exemptions with reasons, kinds); tenant_table auto-attach; UnitOfWork.allow_archived_write; rule ARCHIVE-001. Rollback: downgrade drops the function and every trigger with CASCADE.

## Progress log
- 2026-11-06: built. `backend/tests/integration/test_a07t13_archived_guard.py` written, not run (end pass). Ruff, pyright and banned patterns run on the touched files.

## Decisions made during this task
DEC-2413
