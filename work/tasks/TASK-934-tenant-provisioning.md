---
id: TASK-934
title: TenantProvisioningWorkflow v1 and the tenant operator commands (Q-01-T45)
spec: SPEC-050
acceptance_criteria: [AC-21, AC-27]
risk_zone: red
status: in-review
epic: Q-01
plan_key: Q-01-T45
branch: q01-t45-tenant-provisioning
created: 2026-10-23
updated: 2026-10-23
---

## Objective
"Re-running a provision with the same key returns the same tenant, a non-US region is refused, and the audit trail names the operator on every step" (Q-01-T45; Q-01 §3 F7, §4.4, §4.5; ADR-156; platform-ops contract §3.5, §3.6).

## Plan
- Settings: `ops_database_url` (Restricted SecretStr). Local runs use the compose `abacus_ops` role. The API and worker never need it.
- `platform/workflow_types.py`: `ProvisionTenantInput` and `ProvisionTenantResult`.
- `platform/workflows.py`: `TenantProvisioningWorkflow` (`tenant_provision:<tenant>`). Named patch points:
  - `tenant_key_v1`: Q-01-T27;
  - `plan_entitlements_v1` and `first_admins_v1`: each needs a migration first (see Not done);
  - `g04_plan_v2`: G-04.
- `platform/provisioning.py`: `start_provisioning` through `dispatch`, on the background class. Its reuse policy allows a new run only after a failure; an open or finished run is not started again. The activity `platform.emit_tenant_provisioned` reads the firm under row-level security (the input is not proof), then records `tenant.provisioned` in the audit trail and the outbox as `system` / `operator:<handle>`.
- `platform/events.py`: `TenantProvisioned` with `tenant_id`, `plan`, `synthetic` and `operator`. It carries no addresses and no key identifiers.
- `identity.api.firm_tenancy`: the firm's `synthetic`, `region` and key state, read under row-level security.
- `platform/api.py`: `SUBSCRIPTIONS`, `WORKFLOWS` and `ACTIVITIES`, so the worker loads the module. Both worker module-list pins are updated.
- `abacus_tools/tenants.py`:
  - `provision`: `provision_firm` as `abacus_ops`, then start the workflow. There is no `--region`.
  - `status --tenant`: read-only.
  - `entitlement`, run by `make entitlement`: as the owner role, the same pattern as `agent_stage`. It writes the row and the `tenant.entitlements_changed` audit event in one transaction. The new row's `valid_from` is the firm's business date.
- Recorder `abacus_tools/workflows/record_tenant_provisioning.py`, history `tenant-provisioning-v1-provisioned.json` and its replay test.
- Tests: `tests/integration/test_tenant_provisioning.py`, which runs against Postgres and a real Temporal.
- Rollback: revert the commit. No schema change.

## What changed
- As planned. The 7 integration tests cover:
  - the same tenant and no second workflow for the same key;
  - the operator on the provisioning request and on every audit row;
  - a non-US region refused by the definer, with nothing written;
  - no `--region` argument;
  - an email address refused as an operator handle;
  - entitlements and `status`;
  - an unknown firm refused.
- Deviation: `status` takes `--tenant` only. `firms` has no slug column, and `abacus_ops` can't read `firm_provisioning_requests`.
- Deviation: the workflow input does not repeat the firm name, which already lives on the firm row.
- DB-001 and TENANT-001 exempt `abacus_tools/tenants.py`, the same exemption `agent_stage.py` has.

## Not done (behind seams, or needs a human)
- **TenantKeyWorkflow (Q-01-T27)** doesn't exist yet. Until it does, a provisioned firm keeps `kms_key_status = 'none'`, and ADR-156 says such a firm stores no client content. T27 adds the child under `workflow.patched("tenant_key_v1")`. DISPATCH-001 bans `execute_child_workflow` in modules, so T27 also needs a kernel helper or a rule exception.
- **Plan entitlements in the workflow need a migration.** The app role has only SELECT on `tenant_entitlements`, it has no access to `plans`, and `plans` names no modules. The migration needs a plan-to-modules table, or a definer the worker may call. It should also give `make entitlement` a definer for `abacus_ops`, which removes the owner-role path.
- **First-admin invitations need a migration.** `staff_invitations.invited_by` is a NOT NULL foreign key to `memberships`, and a new firm has no members. The migration needs a nullable `invited_by` plus the inviting operator. Until then the admin addresses ride in the input and nothing is sent.
- **Operations:**
  - an `ABACUS_OPS_DATABASE_URL` secret (`abacus/<env>/db/ops`) on the ops task;
  - the owner secret, while `make entitlement` still uses the owner role;
  - `ops-task.yml` allowlist entries for `abacus_tools.tenants`.

## Progress log
- 2026-10-23: built and tested. The provisioning integration tests, the replay tests, the worker, API and identity unit suites, banned patterns, lint-imports, validate_docs, secrets_scan and check-generated all pass.
