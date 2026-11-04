---
id: TASK-3251
title: A-07-T07 migration 0664 assurance EQR and completion (M1)
spec: SPEC-644
acceptance_criteria: [AC-7]
risk_zone: red
status: in-review
epic: A-07
plan_key: A-07-T07
branch: s27-a07-t07
worktree: /Users/ayushkbhatia/Accrued/abacus-s27
created: 2026-11-04
updated: 2026-11-04
---

## Objective
"Up/down/up passes, a concurrence written by an agent or system actor is refused by the database,
and every new table has forced RLS."

## Plan (red)
- Migration 0664 on 0663 (expand-only): `eqr_reviews`, `eqr_checklist_items`,
  `eqr_digest_cards`, `completion_items`, `subsequent_event_procedures`, insert-only
  `subsequent_events` (trigger `a07_rows_immutable`), `legal_letters`,
  `going_concern_evaluations`, `filings`; `eqr_concurrences` (0077) gains nullable work-item
  columns with CHECKs binding only v2 rows (complete, one per review, the transaction's own
  human actor). Column grants: no DELETE anywhere; digest-card content immutable.
- Phase codes `archiving` and `archived` are already in 0134's CHECK: nothing to add.
- Human-only audit actions gain `eqr.concurred` (also SPEC-314's event) and `eqr.card_reviewed`;
  0664 redefines `abacus_human_only_actions()`; `_human_only_actions.py` regenerated.
- Registry (`assurance/registry.py`): `A07_COMPLETION_TABLES`, INSERT_ONLY, INSERT_COLUMNS,
  UPDATE_COLUMNS; `schema_check.IMMUTABLE_TABLES`; the tenant-isolation table list.
- Classification tags live on the contract models (T04); text carrying client facts is sealed
  (`na_basis_sealed`, `description_sealed`, `fs_effect_sealed`, `basis_sealed`).
- Tests: `tests/integration/test_a07t07_eqr_completion_migration.py`.
- Rollback: the downgrade drops the tables and columns and restores 0662's list.

## Progress log
- 2026-11-04: built. `_SHA` kept single-braced because it is interpolated into f-strings (the
  0642 lesson). A digest-card CHECK bound to `app.actor_kind` would refuse the system's later
  `superseded_by` update on a reviewed card, so the card's CHECK names only the human kind.

## Decisions made during this task
DEC-2232.
