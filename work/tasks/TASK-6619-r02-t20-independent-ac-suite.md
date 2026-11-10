---
id: TASK-6619
title: "R-02-T20: ADR-078 independent AC suite for R-02's amber migration and services (T05, T09, T11, T12, T15, T16)"
spec: SPEC-646
acceptance_criteria: [AC-4, AC-12]
risk_zone: amber
status: in-review
branch: s34-r02-t20
worktree: /Users/ayushkbhatia/Accrued/abacus-s34
created: 2026-11-10
updated: 2026-11-10
plan_key: R-02-T20
---

## Objective
Suites headed `ac-test-author notanaskhan` pass and fail if any portal DTO carries a materiality,
threshold, policy or agent field.

## Plan (amber)
1. `backend/tests/unit/portal/test_r02t20_independent.py`, written from R-02 §3, AC-4, §5 and §6:
   - the pack-rule scan over every `/v1/portal` request and response schema in the OpenAPI
     (refs, unions, items followed), with a planted `performance_materiality` proving it bites;
   - INV-4's scope matrix through `scope_covered`;
   - I-AGENT-NEVER, `mfa_recent` and `scope_only` on the five client decisions; no firm role
     holds a portal-half cell;
   - the decider rule (owner or approver of record; SKE designee on an attest package);
   - `Idempotency-Key` on the five decision routes; `seen_hash` in every approval body;
   - 22,250 from the frozen snapshot; no amount in the acknowledge body; the seen-hash moves with
     the snapshot or version; an older or already approved draft answers `item_changed` with no
     write; a draft is only approved.
2. No production code. Rollback: delete the file.

## Progress log
- 2026-11-10: written; run at the S34 end pass.
- Not duplicated: T05's insert-only and human-only rules run in
  `tests/integration/test_r02t05_deliverables_governance_migration.py` (Postgres); T12/T16's
  per-member privacy in the assurance unit suites. Idempotency replay (same key, one decision) is
  the kernel's (`kernel/uow/idempotency`), covered by R-02-T11's suite; here only the header's
  presence on every route.
