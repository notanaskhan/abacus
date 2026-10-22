---
id: TASK-416
title: Audit attribution - scope, on-behalf-of and policy_ref on audit_events [mig 0096] (Q-02-T16)
spec: SPEC-304
acceptance_criteria: [AC-1]
risk_zone: red
status: done
epic: Q-02
plan_key: Q-02-T16
branch: q02-t16-audit-attribution
created: 2026-10-22
updated: 2026-10-22
---

## Objective
"Every new agent audit row names the person it acted for, a policy row without policy_ref is refused, and the migration passes up, down and up."

## Plan
- Migration 0096.
- `kernel.db.TenantContext.on_behalf_of_user_id`.
- `kernel.uow.Scope` and `tx.record(scope=)`.
- The identity agent and system contexts.
- The schema_check insert columns.
- Rollback: `alembic downgrade 0095`, then revert.

## What changed
- **`audit_events`:**
  - new columns `engagement_id`, `work_item_id`, `on_behalf_of_user_id` and `policy_ref`, with partial indexes on `(tenant, engagement, seq)` and `(tenant, work_item, seq)`;
  - `actor_kind` may be `policy`, which stays dormant (DEC-53) and needs a `policy_ref`;
  - agent rows must name the person they acted for. The check is NOT VALID, so history from before the column is left alone.
- **`TenantContext`:** an optional `on_behalf_of_user_id`. `agent_context_for_run` fills it with the initiator and `system_context_for_run` with the run's person.
- **`tx.record(..., scope=Scope(engagement_id, work_item_id))`:** the unit of work writes the scope and the person on every audit row.
- **Not done:** modules don't pass `scope` yet. They adopt it as they touch their writes, and once they do, DEC-121's resolvers can go.

## Progress log
- 2026-10-22: the new `tests/integration/test_audit_attribution.py` passes. An agent row without its person is refused, a policy row without `policy_ref` is refused, and the unit of work writes scope and person. `test_schema_check_db` (up, down and up) and `test_tenancy` pass: 226 in all.
