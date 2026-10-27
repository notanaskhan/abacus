---
id: TASK-1605
title: Migration evidence_scope, client-scoped evidence and same-client fulfilment (N-01-T06)
spec: SPEC-380
acceptance_criteria: [AC-20, AC-21]
risk_zone: red
status: in-review
epic: N-01
plan_key: N-01-T06
branch: s13-n01-t06
created: 2026-10-27
updated: 2026-10-27
---

## Objective
Land ADR-158's schema: client-scoped evidence, scope and folder columns, version channel, supersede and virtual-split columns, and the same-client fulfilment trigger.

## Plan
- Migration `0270_evidence_scope.py` (down 0244; re-chained at the batch merge). Backfill client, work item and channel; nullable `engagement_id` with the scope CHECK; FKs to clients and work items; BEFORE INSERT fill triggers so existing inserts are unchanged; plain version FK on fulfilments plus `fulfilment_same_client`; downgrade guard.
- `evidence/models.py`, `evidence/registry.py` (insert columns).
- ADR-158 accepted; DEC-705; ADR backlog.
- Test `tests/integration/test_n01t06_evidence_scope_migration.py`: backfill, fill trigger, client-scoped item, same-client cross-engagement fulfilment allowed, other client refused, supersede rule, downgrade guard, down/up/down/up with the schema check.
- Rollback: downgrade 0270 (refuses once client-scoped data exists).

## Progress log
- 2026-10-27: built; the migration test runs in the end-of-batch pass (testcontainers).
