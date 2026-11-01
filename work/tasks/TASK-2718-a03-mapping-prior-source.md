---
id: TASK-2718
title: A mapping set's prior-year source and Granite Peak's FY2025 mapping
spec: SPEC-580  # A-03 §4.2 mapping_sets, §3 F6
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
epic: A-03
plan_key: A-03-T16
branch: s22-a03-prior-file
worktree: /Users/ayushkbhatia/Accrued/abacus-s22
created: 2026-11-01
updated: 2026-11-01
---

## Objective
AUD-31 f's run line, "prior-year codes from the FY2025 mapping": Granite Peak has no FY2025
engagement, so the prior year comes from the predecessor auditor's mapping file. The C9 v2 run
body already names `prior_source` and `predecessor_evidence_version_id`; nothing read them.

## Plan (amber)
- Migration 0582 on 0612 (expand-only): three insert-only columns on `mapping_sets` and a CHECK.
  Rollback: downgrade drops them and restores the five-column insert grant.
- `ledger.compute.mapping.predecessor_keys` (pure); `ledger.mapping.create_mapping_set` stores the
  source; registry insert columns.
- `assurance.mapping._prior` by the set's source; `mapping_live.run_start` parses the file.
- Errors `predecessor_file_mismatch`, `predecessor_unreadable` (422); contract §6.
- Slice: Simone uploads the FY2025 mapping and starts the run with it.

## Done (DEC-1769)
- All of the plan. Tests: `tests/unit/ledger/test_predecessor_keys.py` (8 passed),
  `tests/integration/backfill/test_a03_predecessor_mapping.py` (4 passed); A-03-T08, T14 and T17
  mapping suites (13 passed); `test_schema_check_db.py` (192 passed);
  `test_scenario_sampling.py` (1 passed: 122 keys from the file, Caleb's confirm still holds).

## Progress log
- 2026-11-01: built. Two slips: `Ref` takes identifiers only (an audit `after` carrying the
  source was refused), and SQLAlchemy's JSONB writes `None` as JSON null unless `none_as_null`,
  which the jsonb CHECK refuses.
