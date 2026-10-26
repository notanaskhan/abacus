---
id: TASK-1327
title: Consumer contract tests for the intake and import stubs (P-07-T45)
spec: SPEC-332
acceptance_criteria: [AC-23]
risk_zone: green
status: in-review
epic: P-07
plan_key: P-07-T45
branch: s10b-client-intake
created: 2026-10-26
updated: 2026-10-26
---

## Objective
"The suite asserts the CLI-06g tallies 204, 8 and 0 and the masked TIN shape in import rows."

## Plan
- `backend/tests/contracts/intake_import/test_intake_import_consumer.py`: CLI-06's consumer
  view of the OpenAPI document and the models: the g tallies round-trip through
  `ClientImportOut`/`ClientImportCountsOut`, a row's `tin` is `MaskedTinOut` by reference
  (kind, presence, last four) and an offshore reader gets it masked, the dedupe card's fields,
  the commit body and answer, the error statuses of §6.
- No migration, flag or matrix edit. **Rollback**: delete the file.

## Progress log
- 2026-10-26: planned.
