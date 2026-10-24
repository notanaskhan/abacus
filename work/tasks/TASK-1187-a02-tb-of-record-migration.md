---
id: TASK-1187
title: "A-02-T04: migration 0149 - ledger_snapshots.label and generated source_kind; the second immutability layer on trial_balance_versions"
spec: SPEC-333
acceptance_criteria: [AC-1, AC-2, AC-3, AC-32, AC-33, AC-34]
risk_zone: red
status: in-progress
epic: A-02
plan_key: A-02-T04
branch: s8a-tb-of-record
created: 2026-10-25
updated: 2026-10-25
---

## Objective
"The migration passes up/down/up on a staging copy, no existing snapshot row is updated, and trial_balance_versions refuses UPDATE, DELETE and a non-human actor for abacus_app." (A-02-T04)

## Plan (red zone)
- **Already built (migration 0073, SPEC-309)**: `trial_balances` (UPDATE only on `current_version_no`) and insert-only `trial_balance_versions` with `CHECK (actor_kind = 'human')`, a reason on every version after the first, composite FKs to same-entity snapshots. Not repeated.
- **Migration `0149_tb_of_record_labels.py`** (`down_revision = "0146"`; the main session re-chains):
  - `ledger_snapshots.label text NOT NULL DEFAULT 'standard'` with `CHECK (label IN ('standard','interim','prior','budget','preliminary'))`; `GRANT INSERT (label)` to `abacus_app`. A constant default is a catalogue-only change: no row is rewritten or updated and no row trigger fires (ADR-004).
  - `ledger_snapshots.source_kind text GENERATED ALWAYS AS (…) STORED` (`import_%` -> import, `fake` -> fake, else connector). Postgres rewrites the table for a stored generated column without firing row triggers; nobody can insert or update it.
  - Second layer on `trial_balance_versions`: `BEFORE UPDATE OR DELETE` and `BEFORE TRUNCATE` triggers calling the existing `ledger_immutable()` (the epic's "IO = revoked plus a trigger"; 0073 only revoked).
  - Downgrade refuses while any snapshot carries a label other than `standard` (it would lose it); otherwise drops the triggers and both columns.
- **Registries**: ledger `INSERT_COLUMNS["ledger_snapshots"]` gains `label`; `schema_check.IMMUTABLE_TABLES` gains `trial_balance_versions`; `test_schema_check_db.py` expectations follow. `LedgerSnapshot` model maps `label` (server default) and `source_kind` (`Computed`).
- **Tests**: `backend/tests/integration/test_tb_of_record_schema.py` (up/down/up with a pre-existing snapshot that comes back unchanged; label default and CHECK; source_kind per source; the app inserts a label but never source_kind; versions refuse UPDATE, DELETE and a non-human actor for the app; the trigger refuses UPDATE, DELETE and TRUNCATE for the superuser; the downgrade guard).
- **Rollback**: `alembic downgrade 0146` (refused while non-standard labels exist).

## Progress log
