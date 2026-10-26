---
id: TASK-1350
title: Consumer contract tests for the intake and import stubs, independent (P-07-T45)
spec: SPEC-332
acceptance_criteria: [AC-23]
risk_zone: amber
status: in-review
epic: P-07
plan_key: P-07-T45
branch: s10c-tests
created: 2026-10-27
updated: 2026-10-27
---

## Objective
"The suite asserts the CLI-06g tallies 204, 8 and 0 and the masked TIN shape in import rows."

## Plan
- **File:** `backend/tests/contracts/intake_import/test_intake_import_consumer_adr078.py`, from
  `docs/contracts/intake-import.md` §3, §6 and §8 and CLI-06 g: the OpenAPI document as the
  consumer reads it (no plain TIN anywhere, the row's TIN the masked shape by reference, the
  tallies, the commit answer, the key headers), and the offshore mask over a row.
- **Rollback:** delete the file.

## Progress log
- 2026-10-27: planned and written.
- 2026-10-27: 17 passed. `MaskedTinOut.presence` is `on_file` or `applied_for`; `engagement_status` is the `EngagementStatus` schema by reference.
