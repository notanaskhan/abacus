# platform

Firm budgets and metering, entitlements, the capabilities read and the search slot. Reachable from every module above identity (`MODULE_DEPENDENCIES`).

## Tables (`registry.py`)
- `tenant_entitlements` (F-03-T28, migration 0088; ADR-148): which modules a firm may use (`attest`, `internal_audit`, `group_audit`, `statements_studio`, `office_addins`, `insights`), with seats, the agent-minute allowance and validity dates. The app reads it under the firm's row-level security and writes nothing; the operator console and the scenario loader set it.
- `plans` (0088): global plan codes; no app privilege.
- `platform_controls`, `platform_control_changes`, `firm_provisioning_requests` (Q-01-T19, migration 0086; ADR-157): global, reached only through definer functions (`platform_control_state` for the app; `set_platform_control` and `provision_firm` for `abacus_ops` only).

## Tenant provisioning (Q-01-T45; `provisioning.py`, `workflows.py`; ADR-156)
- `abacus_tools.tenants provision` calls `provision_firm(...)` as `abacus_ops` (`ops_database_url`), then `start_provisioning(input)` starts `TenantProvisioningWorkflow` (`tenant_provision:<tenant_id>`, background class). A run that is open or completed is never started again (the same idempotency key returns the same tenant); a failed one may be.
- v1 runs one activity, `platform.emit_tenant_provisioned`: it reads the firm under its row-level security, then records `tenant.provisioned` (audit and outbox `TenantProvisioned`: `tenant_id`, `plan`, `synthetic`, `operator`) as `system` / `operator:<handle>`.
- Patch points, each a later change behind its own `workflow.patched(...)` before the emit step: `tenant_key_v1` (Q-01-T27's child `TenantKeyWorkflow`), `plan_entitlements_v1` and `first_admins_v1` (each needs a migration first: a writer the worker may use for `tenant_entitlements`, and a staff invitation no member sent), `g04_plan_v2` (G-04). The v1 history `tenant-provisioning-v1-provisioned.json` must keep replaying.
- `make entitlement` (`abacus_tools.tenants entitlement`) writes one `tenant_entitlements` row and `tenant.entitlements_changed` as the operator, through the owner role, until `abacus_ops` has a definer for it.
- The worker loads this module (`SUBSCRIPTIONS`, `WORKFLOWS`, `ACTIVITIES` in `api.py`).

## Budgets and metering (SPEC-007)
The gateway owns the data; this module authorises and serves it.

- `GET /v1/budget` (`budget.read`): the firm's monthly budget, the plan limit and this month's spend.
- `PUT /v1/budget` (`budget.manage`, fresh MFA): sets the budget, which is audited as `budget.updated`. The soft limit must be at most the hard limit, and the hard limit at most the plan limit.
- `GET /v1/metering?period=day|month` (`budget.read`): spend per engagement and agent.

## Entitlements (F-03-T28; `entitlements.py`)
- `entitlement(tenant, module)` returns the firm's enabled row valid on the business date, or `None`; `check_entitlement` raises `EntitlementRequired` (403 `entitlement_required`, facts `module`); `require_entitlement(module)` is the FastAPI dependency for a route.
- Module rollout is an entitlement, never a feature flag: the flag registry refuses `ff.*` names and names whose area is an entitlement module.

## Capabilities (F-03-T30; `capabilities.py`; ADR-145)
- `GET /v1/me/capabilities?engagement_id=` (route marker `own`: any signed-in member, about themselves): the matrix evaluated for the caller through `identity.allowed_actions`, which records no authorisation check. Returns `capabilities`, `roles` (code and label), `flags`, `entitlements` (modules held), `office_id`, `tz`, `mfa_recent_until`, `server_now`, `clock_mode`, `portal` (`shell` and `scopes`, client users only) and `nav` (firm settings areas; all `none` on an engagement's capabilities). A walled or unknown engagement answers 404.
- What it offers is never a grant: every action is still checked by `authorise` when it is taken.

## Search slot (C15; `slots.py`)
`register_search_projection(object_type, builder)`; an unregistered type is never indexed (fail closed).
