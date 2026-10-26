# Contacts and portal access · CLI-04 (v1)

| Field | Value |
|---|---|
| Register row | Screen-family contracts in `docs/contracts/README.md` |
| Version | v1 |
| Status | live (P-07-T25, 2026-10-24; DEC-300 to DEC-302); stub P-07-T17 |
| Provider epic | P-07 (`organisations` for contacts, `identity` for grants and unlocks) |
| Consumers | CLI-04 (P-07-T24); the consumer suite P-07-T18; P-08 (portal sign-in reads the grants); P-09 (delegated requests) |
| Freeze sprint | the sprint review after the stub (P-07 §8.1) |
| Flag | `contacts.v2` (default off, created 2026-10-24, expires 2027-04-21 under DEC-137's override) |
| Spec | `docs/specs/SPEC-321-clients-engagements-v2.md`; P-07 Story 2.1 |
| ADRs | ADR-139 (P-36), ADR-140 (P-39), ADR-146 (client access in grants), ADR-005, ADR-031; DEC-35, DEC-43, DEC-129, DEC-211, DEC-226 |

## 1. Purpose
Consumers can rely on a client's contacts list on the P-36 envelope with CLI-04's header counts ("3 active · 1 invited · 2 not invited") and the delegated-requests footer ("10 + 9 + 2 + 2 + 1 = 24", "PBC received 11 of 24"); a contact drawer with roles per entity, grants, sign-in history and delegated requests; contact create and edit; invitations that carry grants (a grant role, a scope and, for a delegate or third party, the request items it is limited to), with MFA from firm policy and a 14-day single-use link; resend, revoke (requests stay with the client), change scope and unlock.

**Behaviour.** With `contacts.v2` off every route below answers 404. With it on, every route is live (P-07-T25): pending grants and a contact invitation in one unit of work (DEC-300), the email from the firm's `portal.invitation` template (DEC-301), the list's states and footer as DEC-302 reads them. Before P-07-T25 each answered 501 `not_implemented`.

## 2. Who may call it
Matrix: `docs/architecture/permission-matrix/organisations.yaml` (`contact.read`, `contact.manage`) and `identity.yaml` (`client_access.grant`, `client_access.revoke`, `contact.unlock`).

| Operation | Method and path | Matrix action | Roles allowed | Agent or system principal |
|---|---|---|---|---|
| Contacts list (CLI-04 a) | `GET /v1/clients/{client_id}/contacts?portal_status=&sort=&cursor=&limit=` | `contact.read` (new) | firm admin, partner (`firm_partner`), practice leader, quality partner, engagement partner, manager, senior, staff, client service | denied |
| Create a contact | `POST /v1/clients/{client_id}/contacts` | `contact.manage` (new) | firm admin, partner, engagement partner, manager, client service | **denied** |
| Contact drawer (O2) | `GET /v1/contacts/{contact_id}` | `contact.read` | as the list | denied |
| Edit a contact | `PATCH /v1/contacts/{contact_id}` | `contact.manage` | as create | **denied** |
| Invite (O3, CLI-04 b) | `POST /v1/contacts/{contact_id}/invitations` + `Idempotency-Key` | `client_access.grant` (F-03) | firm admin, engagement partner, manager, client service; `mfa_recent` | **denied** |
| Resend | `POST /v1/invitations/{invitation_id}/resend` | `client_access.grant` | as invite | **denied** |
| Revoke (CLI-04 f) | `POST /v1/invitations/{invitation_id}/revoke` | `client_access.revoke` (F-03) | as invite; `mfa_recent` | **denied** |
| Change scope (CLI-04 e) | `PUT /v1/contacts/{contact_id}/access` | `client_access.grant` | as invite | **denied** |
| Unlock (CLI-04 d) | `POST /v1/contacts/{contact_id}/unlock` | `contact.unlock` (F-03) | firm admin, security admin, engagement partner, manager, client service; `mfa_recent` (DEC-303) | **denied** |

No client role holds any of these actions. A walled client answers 404 on every route (INV-3, DEC-43); staff sign-in locks are unlocked only by IT/Security (`security_admin`, DF-24), never here.

## 3. Models
Code: `backend/src/abacus/modules/organisations/contacts_contract.py`. Tags: **C** confidential, **I** internal.

- **`ContactsPage`** = the P-36 envelope of `ContactRowOut` + `summary` I (`ContactCountsOut`: `active`, `invited`, `not_invited`, `locked`) + `delegated` I (`DelegatedFooterOut`: `parts` (the non-zero per-contact delegated counts in row order), `total` (their sum), `received`). `counts` per portal status.
- **`ContactRowOut`**: `id` I, `name` C, `party_kind` I (`person`, `organisation`, `group`), `email` C, `roles` C (`ContactRoleOut`: `role` I (P-07 §4.2 M3 codes), `scope_kind` I (`client`, `client_entity`), `scope_id` I, `scope_name` C, `title_text` C), `portal_status` I (C2 `invitation`), `invited_on` I, `expires_on` I, `mfa_enrolled` I, `last_seen_at` I, `delegated_request_count` I, `invitation_id` I (the contact's newest invitation while it is Invited, Active or Locked, else null: what Resend and Revoke take; ED-049, P-07-T33), `allowed_actions` I.
- **`ContactDetailOut`**: `contact` C, `grants` I (`GrantOut`: `id`, `role` (ADR-146 grant roles), `scope_kind` (grant scope kinds), `scope_id`, `request_item_ids`, `status` `pending`/`active`/`revoked`, `granted_at`), `sign_ins` I (`SignInEventOut`: `kind` `signed_in`/`code_failed`/`locked`/`unlocked`, `at`), `delegated_request_ids` I, `version` I.
- **`ContactIn`** / **`ContactPatchIn`** (`seen_version`; absent = unchanged; `roles` replaces) → **`ContactOut`** (`contact`, `version`).
- **`InvitationIn`**: `grants` I (1–20 `GrantIn`: `role`, `scope_kind`, `scope_id`, `request_item_ids`), `expires_in_days` I (always 14). → **`InvitationOut`**: `invitation_id`, `contact_id`, `grants`, `mfa_policy` (`required_by_firm`, `optional`), `sent_at`, `expires_at`, `portal_status` (`invited`). **Never the token or link**: it goes only in the firm-branded email.
- **`InvitationRevokedOut`**: `invitation_id`, `contact_id`, `revoked_grant_ids`, `kept_request_item_ids`, `revoked_at`.
- **`ContactAccessIn`** (`seen_version`, the whole grant set after the change) → **`ContactAccessOut`** (`contact_id`, `grants`, `version`).
- **`ContactUnlockedOut`**: `contact_id`, `portal_status`, `unlocked_at`.

## 4. Status words
`invitation`: `not_invited` Not invited · `invited` Invited (sub-line "Sent {date} · expires {date}") · `active` Active · `locked` Locked · `deactivated` (ADM-02 only). Grant statuses are the grant table's.

## 5. Human-only actions
Every write denies `agent` and `system` at the matrix (INV-1, P-07 §4.4); the live routes also require a live human and, for grants and revokes, recent MFA.

## 6. Errors
| Status | Body | When |
|---|---|---|
| 404 | `{"detail": "not found"}` | `contacts.v2` off; a walled or unknown client, contact or invitation |
| 501 | `{"detail": "not_implemented"}` | the flag on, before P-07-T25 |
| 409 | `{"detail": "contact_exists"}` | create with an email already on the client |
| 409 | `{"detail": "stale_version", "facts": {"contact_id": "…"}}` | edit or change scope with an old `seen_version` |
| 409 | `{"detail": "gate_unmet", "facts": {"gate": "G1", "client_id": "…"}}` | a full-client grant before any engagement of the client is Accepted (intake grants excepted, OQ-11) |
| 409 | `{"detail": "invitation_expired"}` · `{"detail": "invitation_used"}` | catalogued for the firm side; opening a link older than 14 days or already used answers P-08's one 404 (DEC-275, DEC-300) |
| 422 | `{"detail": "invitation_invalid", "facts": {…}}` | grants across more than one engagement, or a contact with no address (DEC-300) |
| 409 | `{"detail": "contact_bound"}` | changing the address of a contact that already signs in (its address is the person's own; DEC-303) |
| 409 | `{"detail": "illegal_transition"}` | inviting an active contact (use Change scope), or changing the scope of one never invited |
| 409 | `{"detail": "consent_required", "facts": {"engagement_id": "…"}}` | an invitation or change of scope that delegates a request of an engagement holding a `tax_return` work item, without the client's C19 `third_party_disclosure` consent (ADR P-12; R-01-T13, DEC-388): nothing is written |
| 422 | `{"detail": "scope_outside_client", "facts": {…}}` | a grant scope or delegated request that is not the contact's client's |

## 7. Audit and outbox events
| Event | Written when | Payload (no Restricted data) |
|---|---|---|
| `contact.created` · `contact.updated` (audit; outbox `contact.created`) | create, edit | contact id, field names |
| `contact.invited` (audit, outbox) | an invitation with its pending grants | contact id, invitation id, grant ids |
| `invitation.resent` · `invitation.revoked` (audit) | resend, revoke | invitation id |
| `client_access.granted` · `client_access.revoked` (outbox, F-03) | grants change | grant ids |
| `contact.access_changed` (audit) | change scope | contact id |
| `contact.unlocked` (audit) | unlock | contact id, actor |

## 8. Example payloads
Brightwater Hale, synthetic; ids are placeholders.

`GET /v1/clients/{northwind}/contacts` (CLI-04 a): six rows; `"summary": {"active": 3, "invited": 1, "not_invited": 2, "locked": 0}`; `"delegated": {"parts": [10, 9, 2, 2, 1], "total": 24, "received": 11}`.

`POST /v1/contacts/{harborline}/invitations` `{"grants": [{"role": "third_party", "scope_kind": "request_item", "scope_id": "…", "request_item_ids": ["…", "…"]}], "expires_in_days": 14}` → 201 `{"portal_status": "invited", "mfa_policy": "required_by_firm", …}`.

## 9. Consumer contract tests
- Stub: `backend/tests/contracts/contacts_access/test_contacts_access_stub.py`.
- Consumers (P-07-T18): shapes, the counts header and the 24-request footer sum.

## 10. Versioning
| Version | Frozen on | Overlap ends | Notes |
|---|---|---|---|
| v1 | | | stub 2026-10-24 (P-07-T17) |

## 11. Open points
- DEC-226: `contact.read` and `contact.manage` are new organisations rows (F-03 named them; they did not exist); the grant, revoke and unlock rows stay identity's; `/v1/invitations/{id}/…` sits beside identity's `/v1/invitations/accept`; the footer's `parts` are the non-zero per-contact counts; the token never appears in a response.
