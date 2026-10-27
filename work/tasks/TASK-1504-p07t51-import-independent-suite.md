---
id: TASK-1504
title: P-07-T51 independent acceptance suite for the bulk import (ADR-078)
spec: SPEC-332
acceptance_criteria: [AC-24]  # walled clients are never a match; Story 3.2 is the epic AC
risk_zone: amber
status: in-review
epic: P-07
branch: s12b-p07t51
created: 2026-10-27
updated: 2026-10-27
---

## Objective
Independent AC tests for P-07-T52: idempotent re-run, auto-match threshold, no merge below 90% without a decision, EIN fingerprint dedupe, hostile cells, SSN refused on real tenants, row decisions audited, file retention.

## Plan (amber)
- One suite, `backend/tests/integration/backfill/test_p07t51_client_import_independent.py`, read from the contract, Story 3.2 and OQ-4. No production code.
- ADR-078's separate session is not met (DEC-644). The suite must pass with T52 unchanged.
- Rollback: delete the file.

## Progress log
- 2026-10-27: written; lint and pyright clean. Run in the S12 batch test pass, stacked on #505.
