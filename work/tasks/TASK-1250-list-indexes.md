---
id: TASK-1250
title: The four composite indexes the plan tests found missing (Q-03-T028 gaps)
spec: SPEC-045
acceptance_criteria: [AC-9]
risk_zone: amber
status: done
epic: Q-03
plan_key: Q-03-T028
branch: lo-indexes
created: 2026-10-26
updated: 2026-10-26
---

## Objective
Q-03-T028's plan tests (TASK-1245) held six list endpoints as gaps: no index served their driving predicate. Add the four indexes they name and clear the gaps, so every one of the twenty endpoints is held to its index.

## Plan
- Migration 0160: `audit_events_target`, `request_items_by_list` (partial, live items), `request_lists_portal`, `memberships_staff`; each leads with `tenant_id`, which row-level security supplies. Created in the migration's transaction (small tables everywhere today).
- `tests/integration/test_q03t028_plan_tests.py`: the six cases lose `gap`, so the plan test requires the index; the gap test has no cases left (pytest reports one skip for the empty set) until a new endpoint is added as a gap.
- Rollback: downgrade 0160 drops the four.

## Progress log
- 2026-10-26: built. Plan tests: 22 passed (20 endpoints planned on their indexes, the index-drop check, the count), 1 skipped (empty gap set). Schema check with the migration roundtrip and migrations env: 197 passed.
