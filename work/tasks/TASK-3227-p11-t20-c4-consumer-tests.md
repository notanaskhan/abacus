---
id: TASK-3227
title: P-11-T20 C4 v1.1 consumer contract tests
spec: SPEC-520
acceptance_criteria: [AC-36]
risk_zone: green
status: in-review
epic: P-11
plan_key: P-11-T20
branch: s26-p11-t20
worktree: /Users/ayushkbhatia/Accrued/abacus-s26
created: 2026-11-03
updated: 2026-11-03
---

# TASK-3227 · P-11-T20 · C4 v1.1 consumer contract tests

**Epic:** P-11 · **Sprint:** S26 · **Type:** TEST · **Zone:** green · **Depends on:** P-11-T19 · **Status:** in-review

## Built
`backend/tests/contracts/p11/test_p11t20_c4_consumers.py`: notices, tax and closes payloads validated through the C4 v1.1 models: field-key pattern, confidence bounds and the 0.90 low-confidence threshold, TIN mask tokens only, the eight refusal reasons, the corrected flag (1099-R box 1b 3,840.00 corrected to 3,310.00), the receipt footing 686.40 + 66.61 = 753.01, tables, and retry refusals.

## Partial
- Runs in the provider's CI with the end pass; the consumer modules (N-04 intake, T-xx, closes) do not read these routes yet, so the suite holds the shapes they will read.

## Progress log
- 2026-11-03: written; ruff and pyright clean; not run (end pass).
