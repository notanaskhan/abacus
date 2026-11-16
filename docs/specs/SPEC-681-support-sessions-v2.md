---
id: SPEC-681
title: Support sessions v2 — amending SPEC-012 per DEC-72 (firm-only approval, one-object scope, Decline, security_admin approver, no emergency second-staff approval)
status: approved
owner: notanaskhan
risk_zone: red
related_adrs: [ADR-007, ADR-014, ADR-020, ADR-024, ADR-028, ADR-030, ADR-145, ADR-147, ADR-151]
related_specs: [SPEC-012, SPEC-680]
amends: SPEC-012
created: 2026-11-15
updated: 2026-11-15
epic: G-04
task: G-04-T01 (TASK-8200)
---

# SPEC-681 · Support sessions v2 (amends SPEC-012)

> **Instructions for coding agents**
> - SPEC-012 stays the spec of record for everything this file does not change. Where they differ,
>   this file wins. The acceptance criteria are the epic's AC-14 to AC-25
>   (`docs/plan/epics/G-04.md` §3.4 and §3.5), adopted verbatim; this file states the changes and
>   each criterion's testable core.
> - Red zone and protected paths (`identity/support.py`, the matrix, migrations). DEC-72 never
>   defaults on silence; OQ-1 is decided below and accepted by Ayush (DEC-5200).

## 1. What changes from SPEC-012
| SPEC-012 | SPEC-681 |
|---|---|
| Scopes `metadata`, `content` | Adds `integration_settings`. A `content` session names exactly one object: `scope_ref_kind` (`work_item` or `engagement`) and `scope_ref_id` |
| Approved by a firm admin with fresh MFA, or, in an emergency, by a second staff member | Approved **only by the firm**: `firm_admin` or **`security_admin`**, with fresh MFA. The staff emergency-approve route is **removed** (404); no HTTP route or console control creates a staff-approved session |
| Statuses `requested`, `active`, `ended`, `revoked`, `expired` | Adds `declined` (terminal): a `firm_admin` or `security_admin` declines a request |
| At most 240 minutes (60 in an emergency) | At most **120 minutes** for every new session (service and a `NOT VALID` CHECK); historic rows stay legal |
| Any staff member may request any scope | A `content` session on a tenant entitled to `tax` (the proxy for holding TRI) needs the staff token's `us_located` attribute, stored on the row (D-OPS-21, RK-26); otherwise 403 `staff_location_required` |
| Requests are free-standing | A request may link the firm user's support conversation (`conversation_id`, service-checked; no cross-module FK) |
| A content session reads the firm | A content session reads only resources whose work item (or engagement) equals `scope_ref_id`; everything else answers 404 (a support scope kind in `visible()`, ADR-145) |
| `support_session.requested` reaches no one | `support_session.requested` reaches the firm's `firm_admin` and `security_admin` members; `support_session.declined` reaches the other approvers (C16) |

Unchanged: staff identities on the separate issuer with MFA; read-only access; `support.request`
audited before each request runs (fail closed); expiry in database time; one open session per
staff member per firm; the firm's "Allow support session requests" switch (G-02-T14; 409
`support_requests_disabled` when off); the quarterly access review. Historic
`support_session.emergency_approved` events stay readable in ADM-07.

## 2. Decision on OQ-1 (DEC-5200)
DEC-72 kept the emergency path for platform security incidents (metadata only, ≤ 60 minutes).
Chapter 01 names this epic's amendment "no emergency second-staff approval", and chapter 01 wins on
scope. **Removed.** Platform incidents use infrastructure logs, not tenant access. If the founders
ever re-affirm DEC-72's carve-out, it ships as an owner-run ops task bound to an open incident
(metadata only, ≤ 60 minutes, firm notified at once), never as an HTTP route or console control.
A `NOT VALID` CHECK (`approved_by_kind IS DISTINCT FROM 'staff'`) refuses staff approval on new
rows, and (`NOT emergency OR scope = 'metadata'`) keeps any historic emergency row metadata-only.

## 3. Data (G-04-T05 migration, modelled on `0023_support_sessions.py`)
`support_sessions`: `scope` CHECK + `integration_settings`; `scope_ref_kind`, `scope_ref_id`;
CHECK (`scope <> 'content' OR scope_ref_id IS NOT NULL`) NOT VALID; `status` CHECK + `declined`;
`approved_by_kind` CHECK + `security_admin`; CHECK (`approved_by_kind IS DISTINCT FROM 'staff'`)
NOT VALID; `declined_by`, `declined_at`; `conversation_id`; `staff_us_located bool NOT NULL
DEFAULT false`; CHECK (`duration_minutes <= 120`) NOT VALID; CHECK (`NOT emergency OR scope =
'metadata'`) NOT VALID. Definer functions: new `decline_support_session`;
`activate_support_session` records the approver's role. `REVOKE UPDATE, DELETE` from `abacus_app`
stays. `firms`: `tenant_code text UNIQUE` (backfilled `tnt_` + initials + sequence),
`onboarding_state` (`invited`, `first_admin_signed_in`, `ready`; default `ready`),
`provisioned_by_staff`, `provisioned_at`. `sandbox_of_firm_id` already exists (migration 0091).

## 4. Interfaces
| Route | Change | Action |
|---|---|---|
| `GET /v1/support-sessions` | Adds `scope_label` (resolved in the firm's context, never returned to staff), `approver_role`, `conversation_id` | `support_session.read` |
| `POST /v1/support-sessions/{id}/approve` · `/revoke` · `/acknowledge` | `security_admin` may approve; approve needs fresh MFA | `support_session.manage` |
| `POST /v1/support-sessions/{id}/decline` *(new)* | Decline a request | `support_session.decline` |
| `POST /v1/support/sessions` (staff issuer) | Adds `integration_settings`, `scope_ref`, `conversation_id`; 409 `support_requests_disabled`; 403 `staff_location_required`; 422 over 120 minutes | staff |
| `POST /v1/support/sessions/{id}/approve` (staff issuer) | **Removed** (404) | — |
| `POST /v1/support/sessions/{id}/end` (staff issuer) | Unchanged | staff |

## 5. Acceptance criteria (epic §3.4, §3.5, verbatim there)
Criterion ids: AC-14, AC-15, AC-16, AC-17, AC-18, AC-19, AC-20, AC-21, AC-22, AC-23, AC-24, AC-25.
- **AC-14** A request is `requested`, the firm's `firm_admin` and `security_admin` are notified, and it shows in ADM-06.
- **AC-15** No console state approves; `POST /v1/support/sessions/{id}/approve` answers 404; a test enumerates every staff route and none moves a session to `active`; the `NOT VALID` CHECK refuses `approved_by_kind = 'staff'`.
- **AC-16** The firm's switch off: 409 `support_requests_disabled`.
- **AC-17** Staff see the scope kind only ("Integration settings only", "Content · 1 return").
- **AC-18** A content request on one work item links the conversation; the firm sees the inline card with the scope resolved in its own context.
- **AC-19** Decline by `firm_admin` or `security_admin`: `declined`, `support_session.declined` audited; other roles read-only.
- **AC-20** Approve with fresh MFA: `active` for the requested minutes; Revoke ends it at once.
- **AC-21** A content session reads only its one object; anything else 404; every request audited before it runs.
- **AC-22** At most 120 minutes, service and CHECK.
- **AC-23** `tax`-entitled tenant, content scope, no `us_located`: 403 `staff_location_required`; the attestation stored on the row.
- **AC-24** The agent never requests, approves, declines or revokes (generated matrix tests); portal principals hold no support-session action.
- **AC-25** No HTTP route creates a staff-approved session; historic emergency events stay readable.

## 6. Live path and the window (ADR-151)
The emergency-route removal is a security change, unflagged. The v2 additions (scope, Decline,
approver role, US attestation) are additive behaviour behind `support.panel_v2` per firm; the
limits apply to new rows. Both merge before the plan's Thu Aug 24 train.
