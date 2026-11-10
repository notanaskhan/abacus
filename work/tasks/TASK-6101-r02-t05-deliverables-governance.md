---
id: TASK-6101
title: "R-02-T05 migration 0710: C10 deliverables, governance bodies, the uncorrected-misstatements acknowledgement"
spec: SPEC-000  # row (R-02-T05)
acceptance_criteria: [AC-1]
risk_zone: amber
status: done
epic: R-02
plan_key: R-02-T05
branch: s30-r02-t05
worktree: /Users/ayushkbhatia/Accrued/abacus-s30
created: 2026-11-08
updated: 2026-11-08
---

## Objective
R-02 §4.2's one expand-only migration: deliverables, audiences, insert-only versions and events, receipts, governance bodies and members, the FK from A-07's governance rows, and the insert-only, human-only uncorrected_misstatement_acknowledgements.

## Plan
- `0710_r02_deliverables_governance.py` on 0701; forced RLS, column-level INSERT/UPDATE grants, `reporting_rows_immutable` on reporting's three insert-only tables, own `acknowledgement_rows_immutable` on the acknowledgement.
- Registries: reporting TABLES/INSERT_ONLY/INSERT_COLUMNS/UPDATE_COLUMNS; assurance `R02_GOVERNANCE_TABLES`; `archive_guard.ALLOWED_KINDS['deliverables'] = ('post_issuance',)` (red: a reissue after lock is a new deliverable).
- Tests: `tests/integration/test_r02t05_deliverables_governance_migration.py` (round-trip db, RLS, insert-only grants and triggers, actor check, A-07 FKs validated, archive guard).
- Rollback: downgrade drops the FKs, tables and function.

## Progress log
- 2026-11-08: built. Written, not run (tests at the end review). ruff and pyright clean on touched files.

## Decisions made during this task
DEC-2700
- 2026-11-08: the client's three decisions join the human-only audit actions (R-02 §4.7):
  `uncorrected_misstatements.acknowledged`, `proposed_entry.client_decided`,
  `statement.approved_by_management`; 0710 redefines `abacus_human_only_actions()`, downgrade
  restores 0668's list. `governance_communication.acknowledged` stays off the list: under DEC-83
  an acknowledgement can arrive through the envelope's system path.
