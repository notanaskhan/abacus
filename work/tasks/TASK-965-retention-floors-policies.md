---
id: TASK-965
title: Retention floors and policies — migration 0112, staff two-person sets, firm policies with the floor trigger, defaults at provisioning and by back-fill (Q-02-T23)
spec: SPEC-051
acceptance_criteria: [AC-2]
risk_zone: red
status: done
epic: Q-02
plan_key: Q-02-T23
branch: s5-compliance
created: 2026-10-23
updated: 2026-10-23
---

## Objective
"Saving a policy below its floor returns 422 below_floor, a floor publishes only after a second platform admin approves, every tenant has a policy per record type once the default set is published, no default or floor value appears in a migration or commit, and the provisioning replay test passes on both histories."

Q-02 AC-30 has no SPEC yet: it lives in `docs/plan/epics/Q-02.md` §3; SPEC-051 (compliance setup) is the nearest spec.

## Plan (red zone)
- **Migration:** `0112_retention.py`. Global `retention_floors` and `retention_policy_defaults`, with no app grant. Tenant `retention_policies` (forced RLS, column grants, guard and history triggers) and insert-only `retention_policy_versions`. Definers: `retention_set_import`, `retention_set_publish`, `retention_floors_published`, `retention_apply_defaults`, `retention_floor_of`, the two trigger functions, and the ops-only `retention_defaults_backfill`. Rollback: `alembic downgrade 0111`.
- **Registries:** evidence `registry.py`; schema_check `GLOBAL_TABLES`, `NON_TENANT_TABLES`, `DEFINER_FUNCTIONS` and `OPS_ONLY_FUNCTIONS`, with their expectations.
- **Code:** `evidence/retention.py` and `evidence/retention_routes.py`; matrix rows `retention_policy.read` and `retention_policy.update` (fresh MFA). Provisioning: `platform.apply_retention_defaults` behind `retention_defaults_v1`, with the recorded v4 history. Ops: `abacus_tools.tenants retention-defaults`.
- **Contract:** `docs/contracts/retention.md`.
- **Tests:** `tests/integration/test_retention_policies.py` (7), the replay test (v1 to v4), the route gates (two imports answer 201, publishing answers 200).

## Progress log
- 2026-10-23: built with Q-02-T27 in one batch PR. Decisions in DEC-156. **Mistake made twice:** the portal PRs (#362, #363) shipped after targeted test runs only, and broke `test_q01_public_routes` and the secrets scan on main. This batch fixes both. From now on, a red PR runs `tests/unit tests/acceptance tests/security tests/contracts` before shipping, not only the suites it touches. Worth a CI path filter or a ship-script step.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-156 | sets, floor lookup, lock, back-fill scope, no flag | no |
