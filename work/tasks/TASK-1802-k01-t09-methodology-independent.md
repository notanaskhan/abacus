---
id: TASK-1802
title: Independent AC tests for K-01-T02, T03, T05, T06 (K-01-T09)
spec: docs/contracts/methodology-programs.md; docs/contracts/knowledge-catalog.md
acceptance_criteria: [AC1.6, AC1.9, AC1.10, AC2.3, AC3.3, AC3.5, AC3.6]
risk_zone: amber
status: in-review
epic: K-01
plan_key: K-01-T09
branch: s13r-k01-t09
created: 2026-10-28
updated: 2026-10-28
---

## Objective
ADR-078 suite written from the contracts and K-01 §3.1 to §3.3, not from the implementing tests: problem codes never echo a cell, formulas stay text, drafts hidden from staff at the API, walls on usage counts (INV-3), portal principals refused (INV-4), human-only approve with refusals audited (INV-1, INV-5), effective-date pins and set-once, frozen published steps.

## Plan
- Tests only: `backend/tests/integration/backfill/test_k01t09_methodology_independent.py`. No implementation change.
- Reown up/down/up is K-01-T02's migration test (`test_k01t02_methodology_reown.py`); not duplicated.

## Progress log
- 2026-10-28: written; run in the end-of-batch pass (S13 leftovers).
