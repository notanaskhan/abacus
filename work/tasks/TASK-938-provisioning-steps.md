---
id: TASK-938
title: Provisioning steps - the plan's entitlements and first-admin invitations (Q-01-T45 patch points)
spec: SPEC-050
acceptance_criteria: [AC-24]
risk_zone: red
status: done
epic: Q-01
plan_key: Q-01-T45
branch: q01-t45-provisioning-steps
created: 2026-10-23
updated: 2026-10-23
---

## Objective
Close two of TenantProvisioningWorkflow's patch points (TASK-934): a new firm gets its plan's entitlements and its first administrators' invitations, as the operator, with no hand steps.

## What changed
- **Migration `0107_provisioning_steps`:**
  - `plan_modules`: global, no app privileges, set by operators through `set_plan_module` (`abacus_ops` only). New CLI command: `python -m abacus_tools.tenants plan-module`.
  - `apply_plan_entitlements`: a definer the worker calls. It writes the plan's `tenant_entitlements`, valid from the kernel's Central business date. It refuses a firm not provisioned through `provision_firm`. A retry, or a firm that already holds rows, writes nothing.
  - `invite_first_admin`: a definer for an operator-issued `firm_admin` staff invitation, allowed only while the firm has no active member. A retry returns the same invitation.
  - `staff_invitations.invited_by` becomes nullable, with `issued_by_operator`; a CHECK requires exactly one sender.
- **Workflow:** `PLAN_ENTITLEMENTS_PATCH` and `FIRST_ADMINS_PATCH` are on.
  - The activities are `platform.set_plan_entitlements` and `platform.invite_first_admins`. The latter goes through `identity.api.invite_first_admins`, which emits `staff_invitation.issued` so the existing email path sends each invitation.
  - The v2 replay history is recorded, and v1 still replays.
- **Tests:** three new cases in `test_tenant_provisioning.py` (end to end, the refusals, idempotent retries). Two existing expectations grow to include the new steps.

## Not done
- `KMS_CHILD_PATCH`: the TenantKeyWorkflow child, which arrives with Q-01-T27 (next PR).
- `G04_PLAN_PATCH`: belongs to G-04.

## Progress log
- 2026-10-23: the provisioning, replay, schema-check and identity suites pass, as do the full `schema_check` and `make check-fast`.
