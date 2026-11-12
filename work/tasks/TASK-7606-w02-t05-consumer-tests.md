---
id: TASK-7606
title: W-02-T05 consumer contract tests for the workbench-sessions family
plan_key: W-02-T05
spec: SPEC-653
acceptance_criteria: [AC-L1, AC-L2, AC-V1, AC-V4, AC-C3, AC-C4, AC-R2, AC-R4]
risk_zone: amber
status: in-review
branch: w02-t05-consumer-tests
worktree: /Users/ayushkbhatia/Accrued/abacus-s40
created: 2026-11-12
updated: 2026-11-12
---

## Objective
Consumer tests for the family in the provider's CI: a pytest half against the T02 and T03 stubs
and a TypeScript half validating the E0 fixtures for WB-01 a–g, WB-02 a–f and WB-03 d/d2 against
the OpenAPI document.

## Plan
- `backend/tests/contracts/workbench_sessions/test_workbench_sessions_consumer.py`: ten routes,
  one action each, 501 tracked by an `UNBUILT` set (T09, T10, T20 empty it); per-artboard field
  lists (`ARTBOARD_FIELDS`), so removing a field an artboard reads fails; every field classified,
  titles Confidential; no `hidden`/`wall` field; agent, system, support and portal refused;
  `workbench.enabled` off is 404.
- `apps/web/src/fixtures/contracts/workbench-sessions.contract.test.ts`: each fixture validated
  with `schema-check` (201 bodies by component schema).
- Rollback: delete the two files.

## Deviations
- WB-03 a, a2, b, c, e, f and g read C6 v2 run items, not this family; their payloads are C6 v2's
  (P-10's consumer tests) and W-02-T13's scenarios.

## Progress log
- `2026-11-12` — Both halves written. Run at the S40 end pass.
