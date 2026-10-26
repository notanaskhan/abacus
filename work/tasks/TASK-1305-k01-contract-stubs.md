---
id: TASK-1305
title: Knowledge-catalog and methodology-programs contract stubs (K-01-T01)
spec: K-01 §4.3, §8.2
acceptance_criteria: [K-01-T01]
risk_zone: amber
status: in-review
epic: K-01
plan_key: K-01-T01
branch: s10-k01-knowledge
created: 2026-10-26
updated: 2026-10-26
---

## Objective
Contract first for KNW-01 to KNW-03: classified shapes and 501 routes for the catalog, the
methodology lifecycle, programs and steps; the matrix actions, five flags and status words; the
two contract documents; the generated client.

## Plan
- `methodology/contract.py`: models and routes (three routers), each behind its flag; client 404.
- Matrix `permission-matrix/methodology.yaml`: the SPEC-008 rows moved from `engagements.yaml`,
  `methodology.approve` and `methodology.parse` new, `methodology.manage` amended; the read
  widening deferred (DEC-406).
- Flags `feature-flags/methodology.yaml` (five); status words `methodology_version`,
  `methodology_import`, `knowledge_item`, `parse_flag`.
- Contracts `docs/contracts/knowledge-catalog.md`, `methodology-programs.md`, register rows;
  `make regenerate`, `make generate`.
- Tests `tests/contracts/knowledge/test_k01_stubs.py`.
- Rollback: revert; every flag stays off.

## Progress log
- 2026-10-26: built with K-01-T02 on one branch; tests run in the end-of-batch targeted pass.
