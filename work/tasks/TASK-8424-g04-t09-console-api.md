---
id: TASK-8424
title: "G-04-T09: Platform principal and console API"
spec: SPEC-680
acceptance_criteria: [AC-1, AC-2, AC-3, AC-7, AC-8]
risk_zone: red
status: in-review
branch: g04-t09-console-api
worktree: /Users/ayushkbhatia/Accrued/abacus-s48
created: 2026-11-17
updated: 2026-11-17
plan_key: G-04-T09
---

## Objective
Spec section: docs/plan/epics/G-04.md §4.4. Platform principal and console API on the staff issuer: platform_admin and platform_support_desk roles, staff matrix check, tenant directory and metadata-only definer reads, tenants list and detail, entitlement PATCH with reason, provisioning and sandbox through TenantProvisioningWorkflow, regions, support-session list, plan-request mark-applied.

## Plan (red)
1. `identity.authz.authorise_staff`: the console roles from the staff token's claims against the matrix's staff section, staff MFA within 15 minutes where `mfa_recent`, the check recorded (the route guard sees it); exported from `identity.api`.
2. `platform/console.py`: directory list (tiles over the whole directory, seats without sandboxes) and detail through `platform_directory_list` / `platform_regions_list` on a `platform_transaction`; the plan from `plan_entitlements`; entitlement PATCH as a new insert-only version in the firm's context as the staff member (actor kind support, `staff:<id>`; `tenant.entitlements_changed` in the firm's trail and outbox) plus `platform_audit_record` with a reason fingerprint; `seats_below_used`; regions; support states; plan requests across tenants and mark-applied with the entitlement version.
3. `console_contract.py`: the routes take the staff principal and call the service; provisioning, sandbox and the provisioning read stay 501 (DEC-5416).
4. Tests: `tests/unit/platform/test_g04t09_console.py`.

## Progress log
- `2026-11-17` — Built in the S48 sequential stack (DEC-5416). Lint, pyright and banned patterns clean; the app imports. Red: security review in the end pass. Partial: provisioning, sandbox and the provisioning read still 501 (`provision_firm` and `platform_directory_upsert` are EXECUTE to the owner/abacus_ops only, so the console start and the directory projector wait on an ops grant and an ops-credentialed worker path); a modules change is recorded in the platform audit for the operator (`tenant_entitlements` is operator-written); support history is empty until the session projector (G-04-T10); the `support` actor's RLS on plan_entitlements and plan_change_requests is unverified until the end-pass integration run. Gates and tests run once at the S48 end pass (build first, test last).
