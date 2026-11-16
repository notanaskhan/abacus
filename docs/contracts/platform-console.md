# Platform console (v1)

| Field | Value |
|---|---|
| Register row | epic contract (G-04 §8.1; no C-register contract) |
| Version | v1 |
| Status | stub (G-04-T03) |
| Provider epic | G-04 (N) |
| Consumers | PLT-01, Q-04 runbooks, K-05 (publication kinds), W-01 (catalogue import follow-on) |
| Flag | `platform.console` (global; the read lands with G-04-T09) |
| Spec | `docs/specs/SPEC-680-g04-platform-console-plan-usage-support.md` (AC-1 to AC-13), `SPEC-681` (AC-15, AC-17) |
| ADRs | ADR-141, ADR-165 (staff issuer), ADR-142 (regions), ADR-147, ADR-148, ADR-139 |

## 1. Purpose
Accrued staff provision tenants, change entitlements with a reason, list regions, request support sessions (never approve them), and apply partner-approved plan requests, all on tenant metadata only.

## 2. Who may call it
Staff on the staff issuer only, with MFA. Every route declares one action of the matrix's staff section (`platform_tenant.read`, `.provision`, `platform_entitlements.update`; DEC-5202), so `identity.routing.staff_action` mounts it on `current_staff`; no firm, portal, agent or break-glass principal reaches one. Roles come from the staff token's claims: `platform_admin` and `platform_support_desk` (DEC-5201). The role check on the claims and the global flag read land with G-04-T09; until then every route answers 501 behind the staff token. Code: `backend/src/abacus/modules/platform/console_contract.py`. Typed fixtures: `platform/g04_fixtures.py` (computed tiles and footer).

| Operation | Method and path | Staff action | Task |
|---|---|---|---|
| Directory | GET `/v1/platform/tenants?region=&health=&q=&tile=&cursor=` | `platform_tenant.read` | T09 |
| Drawer | GET `/v1/platform/tenants/{code}` | `platform_tenant.read` | T09 |
| Entitlements | PATCH `/v1/platform/tenants/{code}/entitlements` (reason 20–500, staff MFA; 409 `seats_below_used`) | `platform_entitlements.update` | T09 |
| Provision | POST `/v1/platform/tenants` (Idempotency-Key; 202; 422 `region_not_live`; 409 `tenant_code_taken`) · GET `/v1/platform/provisioning/{workflow_id}` | `platform_tenant.provision` · `platform_tenant.read` | T09 |
| Training sandbox | POST `/v1/platform/tenants/{code}/sandbox` | `platform_tenant.provision` | T09 |
| Regions | GET `/v1/platform/regions` | `platform_tenant.read` | T09 |
| Support sessions | GET `/v1/platform/support-sessions?status=` (scope kind only) | `platform_tenant.read` | T09 |
| Plan requests | GET `/v1/platform/plan-requests?status=` · POST `…/{id}/mark-applied` | `platform_tenant.read` · `platform_entitlements.update` | T09 |
| Request a session | POST `/v1/support/sessions` (SPEC-681; staff marker route, `platform_support_session.request` on the claims) | staff | T05 |

**There is no console route that approves, grants or opens a session** (SPEC-681 AC-15); the staff emergency-approve route is removed in G-04-T05.

## 3. Models
`TenantsOut` (rows plus `TenantTilesOut` counts that ignore the tile filter: 6 = 4 + 1 + 1, seats 404 of 490 with sandboxes excluded), `TenantRowOut`, `TenantDetailOut` (renewal, seats, included minutes, region storage label, policy-principal availability, support history with the scope kind and a reason fingerprint), `EntitlementsPatchIn`, `ProvisionTenantIn` (exactly two first admins: `firm_admin` and `security_admin`), `ProvisioningOut`, `RegionsOut`, `PlatformSessionsOut`, `PlatformPlanRequestsOut`, `MarkAppliedIn`. **Metadata only** (AC-2): firm display names, tenant codes, counts, module keys, health reason codes, staff and firm-user display names; a generated lint over these schemas (G-04-T16) fails any field that could hold a client, contact, engagement or document name.

## 4. Status words
`tenant_health`, `platform_region`, `support_session`, `plan_request` (DF-31, G-04-T02).

## 5. Audit
`tenant.provisioned`, `tenant.entitlements_changed`, `tenant.sandbox_created` in `platform_audit_events` and the firm's trail (actor kind `support`, "Rowan Achebe (Accrued)"); `plan_request.marked_applied`.
