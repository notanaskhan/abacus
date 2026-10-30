---
id: TASK-2318
title: T-01-T20 ADM-08 integration settings backend
spec: SPEC-501
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: red
status: in-review
epic: T-01
plan_key: T-01-T20
branch: s18-t01-t20
worktree: /Users/ayushkbhatia/Accrued/abacus-s18
created: 2026-10-30
updated: 2026-10-30
---

## Objective
ADM-08's CCH Axcess Tax settings in file-bridge mode: `integration_mappings` (0466), locked cells,
user/office/status mappings with 409 `mapping_conflict`, a versioned and audited save, and the
format check of the latest engine file.

## Plan
- `integrations/engine_settings.py`, model `IntegrationMapping`, registry, api exports
  (`register_engine_file_check`, `engine_return_id`, `FormatCheck`).
- Six routes live in `engine_settings_contract.py`; `FormatCheckOut.returns_read` additive.
- Error catalogue, generated client, contract doc §8, DEC-1364.
- Tests: `tests/unit/integrations/test_t01t20_engine_settings.py`; engine stub contract test.
- Rollback: revert; 0466 downgrade drops the table.

## Progress log
- `2026-10-30` — built (DEC-1364). Unit (11) and contract (47) tests run once. `[skip ci]`.
  End review: tax registers `register_engine_file_check` over T-01-T19's files.

## Handoff
- **Current state:** built, PR open, held for the S18 batch.
- **Exact next step:** T-01-T21 (independent AC tests for T08, T11, T12).
