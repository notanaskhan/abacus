---
id: TASK-3002
title: N-04-T03 migration 0650 notices_v1
spec: SPEC-000  # row
acceptance_criteria: [AC-1]
risk_zone: amber
status: done
epic: N-04
plan_key: N-04-T03
branch: s25-n04-t03 (stacked on s25-n04-t02)
worktree: /Users/ayushkbhatia/Accrued/abacus-s25
created: 2026-11-02
updated: 2026-11-02
---

## Objective
- **[AC-1]** "The migration merges in the Oct 21 batch; insert-only triggers and human-actor
  CHECKs are tested."

## Plan (amber)
- `backend/migrations/versions/0650_notices_v1.py` on 0644 (check `alembic heads` before merge).
- `notices/registry.py`: TABLES, INSERT_ONLY, INSERT_COLUMNS, UPDATE_COLUMNS (TABLE_OWNERS).
- `schema_check.IMMUTABLE_TABLES`: the nine tables → `notice_rows_immutable`.
- Rollback: `alembic downgrade 0644` (drops the eleven tables and the v1 columns; no data yet).

## Acceptance
| Check | Test |
|---|---|
| Down/up with forced RLS | `tests/integration/test_n04t03_notices_v1_migration.py::test_ac_0650_*` |
| Insert-only grants and triggers on the nine tables | `test_ac_the_nine_*`, `test_ac_the_triggers_*` |
| Human-actor CHECKs (sent, reply, confirmation, note) | `test_ac_a_sent_record_*`, `test_ac_an_agency_reply_*`, `test_ac_a_confirmation_*` |
| Sealed TIN; status codes from the vocabulary | `test_ac_a_tin_*`, `test_the_status_checks_*` |

## Progress log
- 2026-11-02: built. Tests and `make check-fast` (schema check) at the S25 end review.

## Decisions made during this task
DEC-2052.
