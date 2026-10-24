---
id: TASK-1130
title: Invitations v2 — migration 0140, the no-oracle preview, accept v2 with template grants, terms and inviter attribution, and auth/start for pending invitees (P-08-T18)
spec: SPEC-320
acceptance_criteria: [AC-12, AC-13]
risk_zone: red
status: done
epic: P-08
plan_key: P-08-T18
branch: s7-p08-invitations
created: 2026-10-24
updated: 2026-10-24
---

## Objective
"Sam Ortiz's preview shows 9 items for Northwind only, acceptance creates request-scoped grants attributed to the inviting person, and a reused or expired token gets the same 404." (P-08-T18; epic Story 4.1; SPEC-320 AC-12, AC-13; DEC-35 14-day single-use links.)

## Plan (red zone)
**Flow (DEC-275).** POR-01d previews the invitation (`POST /v1/invitations/preview {token}`), then "Accept and continue" runs `POST /v1/portal/auth/start {email, invitation_token}`. For a live invitation of the host's firm whose address is the one typed, the invitee (no grant yet) is eligible: their user row is found or provisioned (no membership), the challenge names them and the code email goes out; any other token falls through to the ordinary start, so start still answers one shape. `verify` is unchanged: a right code mints a portal session pinned to tenant and host (ADR-168 §1), which authorises nothing while the person holds no grant (`portal_context` needs a membership and a grant). `POST /v1/invitations/accept {token, terms_version}` with that bearer (the `IDENTITY` principal: a verified email, no account needed) creates the client membership and the template's grants in one unit of work, records `terms_accepted_at`, marks the invitation accepted and its contact active, attributes `client_invitation.accepted` and each `client_access.granted` to the inviter (system actor on behalf of the inviter; grants and their events `by` the inviter), and ends the person's other portal sessions and trusted devices in the firm inside the same unit of work (no `access.changed` is emitted, so the relay does not end the session the person accepted with). If the new grants bring the person under the MFA floor and the session has no second step, the session ends and accept answers `mfa_required` / `mfa_setup_required` with a single-use `mfa_token` (T17's `/mfa` routes finish); otherwise it answers `signed_in` with the landing and the session continues.

**Files.**
- Migration `0140_client_invitations_v2.py` (down_revision `0133`): `client_invitations` gains `kind`, `contact_id`, `grant_template jsonb` (CHECKed shape: role, scope_kind, 1 to 200 scope ids), `terms_version`, `terms_url`, `terms_accepted_at`, `renewal_count` (0 to 2, for T21); INSERT on the new columns, UPDATE on `terms_accepted_at`. Definers: `portal_invitation_preview(host, token_sha, identity)` (host's firm, token's invitation, live, not a staff member's address; misses counted per identity like `invitation_token_find`), `portal_invitation_start(host, email, token_sha, code, resend)` (eligible invitee or the ordinary `portal_sign_in_start`), `portal_invitee_resolve(access_sha, host)` (a live portal session without the membership test, with its email and `mfa_at`), `portal_access_revoke_except(tenant, user, keep)`, `portal_mfa_begin_session(session, user, token, kind, seconds)`. Registered in `schema_check.py` with expectations in `test_schema_check_db.py`.
- `identity/invitations.py`: `INVITATION_DAYS` 14 (SPEC-320 supersedes SPEC-015 Q3; existing pending rows keep their expiry); `create_invitation` takes optional `kind`, `contact_id`, `grant_template`, `terms_version`, `terms_url` (for P-07's CLI-04); `preview_invitation`; `accept_invitation` v2 shared by the legacy OIDC identity and the portal invitee.
- `identity/client_access.py`: `grant_in_unit_of_work` shared by `grant_client_access` and acceptance (one insert path).
- `identity/slots.py`: `register_invitation_parties` (contact's name and organisation, scope label) and `register_contact_activation` (in the caller's unit of work); engagements registers both through `organisations.api`.
- `identity/portal_session.py`: `start_sign_in(..., invitation_token=)`; `portal_invitee(token, host)`.
- `identity/routes.py`: preview route (`PRE_SESSION`), accept v2 body and answer (`session` optional, additive); `routing.py` and `banned_patterns.py` list `/v1/invitations/preview`.
- Organisations: `ContactFacts.organisation_name`, `activate_contact`.
- Scenario slice: Sam's third-party contact (Keystone Retirement Services) and the invitation's v2 fields — `kind delegate`, template `third_party` on 9 `request_item`s of the Northwind audit, `terms_version 1`, the contact.
- Contract doc, C5 stub test (preview moves to served), regenerated OpenAPI and client.

**Tests.** `tests/integration/test_portal_invitations.py` (AC-12, AC-13, start for invitees, staff/expired/used/revoked/malformed/other-host 404, counted misses, single use, inviter attribution, one unit of work, MFA after accept), `tests/integration/test_scenario_portal.py` extended (Sam's 9 items), unit tests for the template validation. Existing invitation tests updated for the 14-day expiry.

**Rollback.** `alembic downgrade 0133` drops the definers and columns; revert the commit. The flag `portal.sign_in_v2` still gates the code email.

## Progress log
- 2026-10-24: plan written.
- 2026-10-24: built as planned (DEC-275). Two closed lists grew: the IDENTITY marker's dependency is now `current_invitee` (the hosted identity or an invitee's portal session; `tests/security/route_checks.py`, `tests/unit/identity/test_routing.py`), and the preview joins the pre-session paths and the not-creating POSTs. SPEC-015's 7-day expiry assertion moved to 14 days (SPEC-320 supersedes it). Found on the way: `grant_client_access` cannot serve acceptance as written (its `authorise` needs the inviter's fresh MFA, and its own unit of work), so both now share `grant_in_unit_of_work`; and `access.changed` from acceptance would end the very session that accepted, so acceptance revokes the other sessions itself. The seeded Sep 2 invitation is expired in wall time (expiry is the database clock): the scenario test reissues it to preview. Tests: `test_portal_invitations.py` 12, `test_scenario_portal.py` extended, `test_portal_slice.py` +1.

- 2026-10-24: security review fixes (DEC-277), failing tests first: the inviter's authority re-checked at acceptance (offboarded, walled, removed, archived each 404 with `client_invitation.accept_refused`); pending invitations revoked on offboarding, a firm role change or leaving the engagement; the second step begun inside the acceptance's transaction; the MFA floor re-applied in `portal_context` per request (new `auth_sessions.device_trusted_at`); the preview bucket keyed on the trusted `CloudFront-Viewer-Address`, else peer plus token-digest prefix; `create_invitation` refuses another client's contact. 0140 gains `portal_session_mark_device`, `client_invitations_revoke_by` and the column. **Human to-do:** the portal distribution's origin request policy must add `CloudFront-Viewer-Address` (the managed AllViewerExceptHostHeader policy forwards viewer headers, not CloudFront's), the ALB must accept only CloudFront, and then `ABACUS_TRUST_CLOUDFRONT_VIEWER_ADDRESS=true` per environment.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-277 | Security review: inviter re-check, eager revocation, the floor in the transaction and per request, the preview bucket, the contact check | No |
| DEC-275 | The invitee's path through start, verify and accept; attribution; revocation inside the unit of work | No (ADR-168 §1, ADR-146) |
