---
id: TASK-1804
title: Independent AC tests for P-07-T55, T47, T57 (P-07-T56)
spec: SPEC-321
acceptance_criteria: [AC-30]
risk_zone: amber
status: in-review
epic: P-07
plan_key: P-07-T56
branch: s13r-p07-t56
created: 2026-10-28
updated: 2026-10-28
---

## Objective
ADR-078 suite from the contracts: evidence never copied, Draft requests invisible to clients, walled (404) or unreleased (409) sources refused, gate kinds appear for the carried team, outbox payloads identifiers only, record activity respects walls.

## Plan
- Tests only: `backend/tests/integration/backfill/test_p07t56_roll_forward_independent.py`.
- The row asks the suite to land before T55's implementation; T55 merged in S14 (#585), so it is committed after and must pass unchanged.

## Progress log
- 2026-10-28: written; run in the end-of-batch pass (S13 leftovers).
