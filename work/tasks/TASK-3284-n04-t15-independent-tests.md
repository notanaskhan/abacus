---
id: TASK-3284
title: N-04-T15 ADR-078 independent tests part 1 for the notices compute and services
spec: SPEC-000  # row (N-04 US-4.1, US-4.3, US-4.4)
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
epic: N-04
plan_key: N-04-T15
branch: s27-n04-t15
worktree: /Users/ayushkbhatia/Accrued/abacus-s27
created: 2026-11-04
updated: 2026-11-04
---

## Objective
Independent tests for the notices compute library, the core and intake.

## Plan (amber)
- `backend/tests/unit/notices/test_n04t15_independent.py`: CP3219A maps to the underreporter
  comparison; preferential income never bracket-checked; the Whitley explanation; Hypothesis purity,
  idempotence and monotone tax; intake guards in order with the 0.90 confidence line; the matrix
  denies every notice write to the agent and every portal principal; TIN-bearing writes onshore.
- No production changes; rollback is deleting the file.

## Progress log
- 2026-11-04: written; ruff clean; run at the end pass. Walls with 404 and no counts are covered by
  `tests/security/test_tenant_isolation.py` and home_counts' tests; part 2 is a later row.
