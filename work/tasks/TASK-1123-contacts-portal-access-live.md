---
id: TASK-1123
title: Contacts and portal access live - contacts_access migration, invitations re-scoped to contacts and grants, resend, revoke, change scope, unlock (P-07-T25)
spec: SPEC-321
acceptance_criteria: [AC-26, AC-27, AC-28, AC-29]
risk_zone: red
status: planning
epic: P-07
plan_key: P-07-T25
branch: s7-p07-contacts
created: 2026-10-24
updated: 2026-10-24
---

## Objective
"Harborline's invitation grants exactly its two delegated requests and is in the pen-test build pinned Fri Feb 12, 2027" (P-07-T25); the routes of `docs/contracts/contacts-access.md` go live, replacing the P-07-T17 stub behind `contacts.v2`.

## Plan (red zone; not built in this session)
- **Migration `0139_contacts_access.py`** (down_revision 0138): `contact_roles(id, tenant_id, contact_id, scope_kind CHECK IN ('client','client_entity'), scope_id, role CHECK IN (the 13 M3 codes), title_text NULL)` through `tenant_table()`; `contacts` + `party_kind text NOT NULL DEFAULT 'person' CHECK IN ('person','organisation','group')` and `version int NOT NULL DEFAULT 1`; `contact_group_members(tenant_id, group_contact_id, member_contact_id)`; `client_invitations` + `contact_id uuid NULL`, `grant_ids uuid[] NULL`, `used_at timestamptz NULL`, `engagement_id` NULL for contact invitations (CHECK: an engagement or a contact), expiry default 14 days; `client_access_grants.user_id` NULL only while `status = 'pending'` (CHECK), so a pending grant can wait for its contact's first sign-in. Registered in `organisations/registry.py` and `identity/registry.py`; INSERT/UPDATE column grants; `schema_check.py` and `test_schema_check_db.py` for any definer function.
- **identity (protected):** `invitations.py` `INVITATION_DAYS` 7 → 14 (DF-24); `invite_contact(ctx, client_id, contact_id, grants)` inside one unit of work: authorise `client_access.grant` (now G2-marked, P-07-T24) per grant scope, the G1 check for a full-client grant (`gate_unmet` unless an engagement of the client is Accepted or later; intake excepted, OQ-11), pending grants through `identity.api.grant_client_access` extended with `status="pending"` and `user_id=None`, an invitation bound to the contact, `contact.invited` audit and outbox; `accept_invitation` activates the contact's pending grants for the provisioned user and stamps `used_at` (single use: `invitation_used`; past `expires_at`: `invitation_expired`); `resend` issues a new token (old hash cleared); `revoke` revokes the invitation and its grants (`access.changed` ends sessions) and returns the delegated request ids kept; change scope diffs the grant set; `unlock_contact` clears the P-08 portal MFA lock (`portal_mfa` state) and audits `contact.unlocked`.
- **organisations:** `contacts.py` (list with `visible_clients`, per-status counts, delegated footer from `requests.api` open-request counts per grant; drawer; create and edit with `seen_version`, roles replace); `contacts_contract.py` routes call the services instead of `_stub`.
- **requests (consumed):** C5 `delegate(request_item_ids, grant)` validates every request item is the contact's client's (`scope_outside_client` 422) and ties them to the grant; a count per contact for the footer.
- **communications (red, consumed):** the invitation email rendered from the firm's database Invitation template (C16) with one call to action and no amounts; no "Accrued".
- **Tests:** `tests/integration/test_contacts_access.py` (Harborline's invite grants exactly its two requests; resend kills the old link; revoke keeps the requests and ends sessions; unlock; G1 refusal; walled client 404; agent and system denied); the stub test's 501 cases become live-route cases; P-07-T26 is the independent suite.
- **Rollback:** `alembic downgrade 0138`; revert; `contacts.v2` off hides every route.

## Progress log
- 2026-10-24: plan written; not built. The row needs identity's invitation acceptance re-scoped (protected), a nullable pending-grant user, the P-08 lock state, C5 delegation counts and the C16 template: more than this session could finish safely after T02, T23 and T24. Next session starts at the migration.
