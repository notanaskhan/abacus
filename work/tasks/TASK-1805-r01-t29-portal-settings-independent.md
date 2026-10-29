---
id: TASK-1805
title: Independent AC tests for R-01-T22 and T26 (R-01-T29)
spec: SPEC-345
acceptance_criteria: [AC-12]
risk_zone: amber
status: in-review
epic: R-01
plan_key: R-01-T29
branch: s13r-r01-t29
created: 2026-10-28
updated: 2026-10-28
---

## Objective
ADR-078 suite from the contract alone: publish atomicity and insert-only versions, fresh MFA, preview read-only with no mutation route and nothing beyond `visible()` (a firm admin without client access cannot preview that client), sample fallback, toggles honoured by the read model, no template text outside the import path.

## Plan
- Tests only: `backend/tests/integration/backfill/test_r01t29_portal_settings_independent.py`.

## Progress log
- 2026-10-28: written; run in the end-of-batch pass (S13 leftovers).
