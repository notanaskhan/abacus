# C5 · Requests and binders, the portal half: portal identity and home (v1.1)

| Field | Value |
|---|---|
| Register row | C5 in `docs/contracts/README.md` (this file is the portal half; the binders and requests half is `c5-requests-binders.md`) |
| Version | v1.1 (additive to C5 v1) |
| Status | stub (POR-01 firm-side recovery, POR-02 home and preferences, `/v1/me` portal fields: P-08-T01, 2026-10-23). Branding and its logo are live (P-08-T05, 2026-10-23); the pre-session family is specified here and **not served** until its decision lands (DEC-139, §2.2) |
| Provider epic | P-08 (schema half: F-03-T26, F-03-T27, F-03-T30) |
| Consumers | R-01 (POR-03, POR-04, POR-14, POR-20 emails), P-07 (CLI-04 unlock and invitations v2), G-02 (ADM-06 MFA policy), N-02, N-01, T-01, T-02, R-02, N-03, A-08, A-09, R-03. Screens: POR-01, POR-02 |
| Freeze sprint | S3 (starts 2026-11-30) with the rest of C5; freeze Fri 2026-12-11 |
| Flags | `portal.sign_in_v2` (identity; default off, created 2026-10-23, expires 2027-01-21) and `portal.home_v2` (portal; default off, created 2026-10-23, expires 2027-01-21). Retired by P-08-T28 |
| Spec | `docs/specs/SPEC-320-portal-identity-and-home.md` (outline; supersedes SPEC-015's expiry and lockout clauses) |
| ADRs | ADR-139 (P-36 conventions), ADR-140 (P-39), ADR-146 (client access grants), ADR-152 (P-45 public routes), ADR-163 (P-11 white label), ADR-005, ADR-031; DEC-34, DEC-35, DEC-58, DEC-59, DEC-63, DEC-129, DEC-139 |

## 1. Purpose
Consumers can rely on a client's portal identity and home: the portal shell and scopes on `/v1/me` (role union, DEC-129), a home read model for one scope that carries client stage codes and client-facing role codes and never a firm status code, an amount, materiality, an agent name or a confidence (INV-4, DEC-19), per-scope preferences, and two firm-side recovery operations (unlock, MFA reset) that only a named person may run (INV-1). Sign-in is passwordless and never reveals whether an email has an account: `start`, `renew` and `preview` answer one shape for every input. The portal is the firm's: no payload carries the word "Accrued" and branding carries Public fields only (ADR-163).

**Stub behaviour.** With its flag off every served route answers 404. With it on, each answers 501 `not_implemented` until its task lands: P-08-T13 (home, preferences), P-08-T21 (unlock, MFA reset). `/v1/me.portal` and `/v1/me.mfa` are `null` until P-08-T07 and T17. The Brightwater Hale portal slice (`stub_from_seed`) arrives with P-08-T08, so the stubs return no fixtures; the screens build on fixture scenarios typed with the generated client.

## 2. Who may call it
Matrix: `docs/architecture/permission-matrix/portal.yaml`, `identity.yaml`.

### 2.1 Served by the stub

| Operation | Method and path | Matrix action | Roles allowed | Agent or system principal |
|---|---|---|---|---|
| Home for one scope (POR-02) | `GET /v1/portal/home?scope_id=` | `portal_home.read` (`scope_only`) | client admin, client contributor whose grant covers the scope; the service also requires a full-client grant (DEC-129), so a third party or K-1-only person gets 404; no firm role | **denied** |
| Per-scope preferences (POR-02 b) | `PUT /v1/portal/preferences` `{scope_id, welcome_dismissed, version}` | `portal_preferences.update` | the signed-in client person, for a scope a grant covers; no firm role | **denied** |
| Unlock a contact's sign-in | `POST /v1/clients/{client_id}/contacts/{contact_id}/portal-unlock` | `contact.unlock` | firm admin, security admin, engagement partner, manager, `client_service` | **denied** |
| Reset a contact's two-step | `POST /v1/clients/{client_id}/contacts/{contact_id}/mfa-reset` + `Idempotency-Key` | `contact.mfa_reset` (`mfa_recent: required`) | security admin | **denied** |
| Me, extended | `GET /v1/me` (exists) | `SELF` (existing) | anyone signed in | as today |

The plan's `portal.home.read` and `portal.preferences.update` are spelt `portal_home.read` and `portal_preferences.update`: a matrix action is `<entity>.<verb>` with one dot (DEC-139). Portal routes take the client principal (`current_member`: the person's own context in the firm, never a break-glass support context) until P-08-T10's portal BFF session and host pinning land (ADR-163 §5); they keep the same action then. The reserved G-02 action `portal_security.manage` is not added until G-02 serves its routes.

### 2.2 Specified, not served by this stub (DEC-139)
These answer before any session exists, so they cannot sit behind `AbacusRouter` (which refuses a route without an action and a principal). An unauthenticated route lives only on ADR-152's public-route list (`abacus.api.public_routes`, ROUTE-001), which is protected and changes only with its own decision. ADR-152 lists `/v1/portal/branding` and `/v1/portal/branding/logo`, both live under the `PORTAL_PUBLIC` route marker since P-08-T05 (DEC-154); the pre-session family still needs an entry (P-08 OQ-2). The routes are served by the named task once that decision lands; their shapes are fixed now in code (`identity/portal_contract.py`, `portal/contract.py`, not routed) and tested by `test_c5_portal_stub.py` and the P-08-T02 consumer tests.

| Operation | Method and path | Authentication | Served by |
|---|---|---|---|
| Branding | `GET /v1/portal/branding` → `PortalBrandingOut` | none · ADR-152 list | P-08-T05 |
| Logo | `GET /v1/portal/branding/logo` → re-encoded PNG (`image/png`, `nosniff`); 404 for a host without one | none · ADR-152 list | P-08-T05 |
| Start | `POST /v1/portal/auth/start` `PortalSignInStartIn` → always **202** `PortalSignInStartOut` | pre-session | P-08-T10 |
| Verify | `POST /v1/portal/auth/verify` `PortalSignInVerifyIn` → `PortalSignInVerifyOut` | pre-session | P-08-T10 |
| Resend | `POST /v1/portal/auth/resend` `PortalSignInResendIn` → `PortalSignInStartOut` | pre-session | P-08-T10 |
| Second step | `POST /v1/portal/auth/mfa` `PortalMfaIn` → `PortalSignInVerifyOut` | pre-session | P-08-T17 |
| Two-step setup | `POST /v1/portal/auth/mfa/setup` `PortalMfaSetupIn` → `PortalMfaSetupOut`; `POST …/mfa/setup/verify` `PortalMfaSetupVerifyIn` → `PortalMfaSetupVerifyOut` | pre-session | P-08-T17 |
| Refresh | `POST /v1/portal/auth/refresh` (cookie, `X-Abacus-CSRF`, Origin) | cookie exception (P-01 pattern) | P-08-T10 |
| Sign out | `POST /v1/portal/auth/sign-out` | `OWN` | P-08-T10 |
| Renew a link | `POST /v1/portal/links/renew` `PortalLinkRenewIn` → always **202** `PortalLinkRenewOut` | pre-session | P-08-T21 |
| Invitation preview | `POST /v1/invitations/preview` `InvitationPreviewIn` → `InvitationPreviewOut`; one `404` for every failure | pre-session | P-08-T18 |
| Accept v2 | `POST /v1/invitations/accept` `InvitationAcceptV2In` (`token`, `terms_version`) | `IDENTITY` (existing) | P-08-T18 (additive; the live route is unchanged by this stub) |

## 3. Models
Code: `backend/src/abacus/modules/portal/contract.py`, `backend/src/abacus/modules/identity/portal_contract.py`; `MeOut` in `identity/routes.py`. Every field is tagged (ADR-031). Confidential: names, labels, titles, client-safe lines, email addresses. Restricted: codes, tokens, TOTP secrets, backup codes (pre-session shapes only; never in a list and never logged). Public: branding. Everything else internal. No TIN, amount or firm status code appears in any portal-half payload. Words come from the frontend copy registry keyed by codes (ADR P-36 code → words).

- **`MeOut`** gains `portal: MePortalOut | null` and `mfa: MeMfaOut | null` (both optional; null for staff and until T07/T17).
  - **`MePortalOut`**: `shell` (`full · k1 · limited · none`), `scopes [MePortalScopeOut {kind (ScopeKind), id, label*, role_label}]`, `nav` (`home · documents · questions · approvals · sign · messages · deliverables`; Approvals only for entity scopes; no bell, DEC-58(d)), `landing` (`home · requests · k1s · governance · intake · component_room · none`, P-08 Story 2.3).
  - **`MeMfaOut`**: `enrolled`, `required` (the DEC-34 floor), `trusted_until`.
- **`PortalHomeOut`** (POR-02): `scope PortalHomeScopeOut {kind, id, label*, sub*, role_label}`, `todos [PortalHomeTodoOut]`, `work_cards [PortalHomeWorkCardOut]`, `binder PortalHomeBinderOut | null`, `team [PortalHomeTeamMemberOut]`, `earlier [PortalHomeEarlierOut]`, `my_k1s [PortalHomeK1Out]`, `recent_threads [PortalHomeThreadOut]`, `notices_info [PortalHomeNoticeOut]` (the last three empty until T-02, N-03 and N-04 register their sources), `first_visit`, `welcome_dismissed`, `all_done`.
  - **`PortalHomeTodoOut`**: `kind` (`upload · answer · sign · deliverables · approve · reconnect · review_statements · control_requests · exceptions · description_approved`), `count`, `state` (`open · none · overdue`; overdue is the request's derived overdue, P-06), `due_date`, `detail`* (the source's client-safe line, e.g. request titles), `facts` (identifiers only), `target {screen (POR-nn), params}`.
  - **`PortalHomeWorkCardOut`**: `work_item_id`, `kind` (C1 registered kind), `title`*, `sub`*, `pill {code, variant}` (codes `getting_started · preparing_return · reviewing_return · reconciling_accounts · filed_and_accepted · finishing_audit · testing_under_way`; variants `state · success · neutral`), `stages [{code, state (done · current · upcoming), facts}]` (client stage codes from P-08-T12 `stages.py`), `note_code` (`waiting_on_k1 · waiting_on_your_k1`), `note_subject`*, `note_date`.
  - **`PortalHomeBinderOut`**: `binder_id`, `done`, `total`, `sorted_count` (firm-attributed: "Brightwater Hale sorted 37 of your files"; never the agent).
  - **`PortalHomeTeamMemberOut`**: `user_id`, `display_name`*, `role_code` (`partner_signs_return · partner · engagement_partner · manager_reviews_return · manager · preparer_day_to_day · preparer · close_preparer · day_to_day_contact · client_service`; OQ-5 derives the day-to-day contact per work-item kind).
  - **`PortalHomeEarlierOut`**: `kind` (`return_filed · extension_filed · engagement_letter_signed · deliverable_released`), `date`, `facts`, `target`. **`PortalHomeK1Out`**: `k1_package_id`, `label`*, `released` (never the firm's package status), `expected_by`. **`PortalHomeThreadOut`**: `thread_id`, `subject`*, `from_name`*, `at`, `unread`. **`PortalHomeNoticeOut`**: `notice_id`, `code` (`agency_notice_in_review`), `subject`*.
- **`PortalPreferencesIn`** `{scope_id, welcome_dismissed, version}` → **`PortalPreferencesOut`** `{scope_id, welcome_dismissed, welcome_dismissed_at, version}`.
- **`ContactPortalStatusOut`** `{client_id, contact_id, portal_status (InvitationStatus), locked_until}`. **`ContactMfaResetOut`** `{client_id, contact_id, mfa_enrolled, trusted_devices_revoked, reset_at}`.
- Not served (§2.2): **`PortalBrandingOut`** (all Public: `firm_name`, `portal_name`, `logo_url`, `address_line`, `help_url`, `privacy_url`, `support_contact_name`, `secured_footer` default false, `sign_in {methods: [email_code], mfa_floor: [owner, signer, approver]}`, `maintenance_banner`; same shape with neutral nulls for an unknown host; no tenant identifier). **`PortalSignInStartIn`** `{email*, link_token?, invitation_token?}` → **`PortalSignInStartOut`** `{challenge_id, code_expires_at, resend_available_at}` for every input. **`PortalSignInVerifyIn`** `{challenge_id, code}` → **`PortalSignInVerifyOut`** `{state: signed_in · mfa_required · mfa_setup_required, access_token?, expires_in?, landing?, mfa_token?}`. **`PortalSignInResendIn`** `{challenge_id}`. **`PortalMfaIn`** `{mfa_token, totp? | backup_code?, trust_device}`. **`PortalMfaSetupIn`**, **`PortalMfaSetupOut`** `{otpauth_uri, manual_key}`, **`PortalMfaSetupVerifyIn`**, **`PortalMfaSetupVerifyOut`** `{backup_codes (8, once), session}`. **`PortalLinkRenewIn`** `{link_token}` → **`PortalLinkRenewOut`** `{accepted: true}` for every token. **`InvitationPreviewIn`** `{token}` → **`InvitationPreviewOut`** `{firm_name, organisation_name*, invitee_name*, invitee_email*, access {kind, item_count, scope_label*}, terms_url, terms_version, expires_at}`. **`InvitationAcceptV2In`** `{token, terms_version}`.

(* confidential)

Beyond the plan's DTO (P-08 §4.3), the stub adds `scope.sub`, `todo.detail`, `work_card.note_subject` and `note_date` (the artboards' household line, to-do lines and the K-1 note name a person or partnership, which identifier-only facts cannot carry), and closes the code sets the artboards show; new codes are additive (DEC-139).

## 4. Status words
From `docs/product/status-vocabulary.yaml` (C2), generated enums only:
- `invitation` (DF-31) on `ContactPortalStatusOut.portal_status`: `not_invited` Not invited · `invited` "Invite pending · expires {date}" (CLI-04 pill "Invited") · `active` Active · `locked` Locked · `deactivated`. Unlock moves `locked` to `active`.
- `request` `overdue` (derived, never stored) is the only status a home to-do reflects, as `state: overdue` (red tint on POR-02 d only).
- Work-item stages and pills are **client stage codes**, never firm statuses ("In review · Manager" and "Draft K-1 · pre-release" never reach the portal). `PortalHomeTodoOut.state` and `PortalHomeStageOut.state` are card positions, not object statuses (status-vocabulary acceptance `NOT_A_STATUS`).

## 5. Human-only actions
Denied to the agent and the system principal at the matrix (`agent: deny`, `system: deny`), proven by `tests/contracts/c5_portal/test_c5_portal_stub.py` and the generated matrix tests; at go-live the services also refuse a non-human context and record the person (INV-1, INV-5):

| Action | Operation | Who |
|---|---|---|
| `contact.unlock` | clear a sign-in or two-step lock | a firm person (admin, security admin, partner, manager, client service); a walled staff member gets 404 (INV-3) |
| `contact.mfa_reset` | remove the factor, backup codes and trusted devices; email the client | security admin with fresh MFA (P-08 OQ-1) |
| `portal_home.read`, `portal_preferences.update` | the client's own reads and preferences | a client person only; every firm role and the agent denied |

Sign-in, two-step and invitation acceptance are the client's own acts through the pre-session family; no firm or agent principal can perform them.

## 6. Errors
Codes are reserved for the implementing tasks; 409 and 422 codes enter `docs/architecture/error-codes.yaml` when the classes that raise them land. The 401, 410, 423, 429 and 503 answers of the pre-session family need new kernel error mappings, added with P-08-T10 (none exists today). Facts are identifiers only (ADR-139).

| Status | Body | When |
|---|---|---|
| 404 | `{"detail": "not found"}` | flag off; a scope no grant covers; no full-client grant (third party, K-1 only); a walled, other-firm or unknown client or contact (INV-3, INV-4) |
| 501 | `{"detail": "not_implemented"}` | stub, flag on |
| 409 | `{"detail": "portal_preferences_stale", "facts": {"version": 3}}` | preferences version mismatch |
| 401 | `{"detail": "code_mismatch", "facts": {"tries_left": 2}}` | wrong sign-in code (T10) |
| 423 | `{"detail": "sign_in_locked", "facts": {"locked_until": "2026-09-14T14:37:00Z"}}` | third wrong code in the window; also for an email that matches no one (no oracle) (T10) |
| 410 | `{"detail": "code_expired"}` | code older than 10 minutes (T10) |
| 429 | `{"detail": "resend_too_soon", "facts": {"resend_available_at": "…"}}` | resend before the countdown (T10) |
| 401 / 423 | `mfa_mismatch {tries_left}` / `mfa_locked {locked_until}` | wrong or locked second step (T17) |
| 503 | `{"detail": "sign_in_paused"}` | the firm's `portal_sign_in_paused` control (Story 7.3) |

`locked_until` and `resend_available_at` are ISO 8601 UTC timestamps (`2026-09-14T14:37:00Z`), which `check_facts` accepts as identifier facts.

## 7. Audit and outbox events
Audit events (UoW `tx.record`, identifiers only; IP, device and session captured per DEC-60; P-08 §4.6): `portal.sign_in.code_requested`, `portal.sign_in.succeeded`, `portal.sign_in.failed`, `portal.sign_in.locked`, `portal.sign_in.unlocked` (names the person who unlocked), `portal.sign_in.paused`, `portal.sign_in.resumed`, `portal.mfa.enrolled`, `portal.mfa.verified`, `portal.mfa.failed`, `portal.mfa.reset`, `portal.backup_code.used`, `portal.device.trusted`, `portal.device.revoked`, `portal.link.renewed`, `client_invitation.accepted` (exists; attributed to the inviter, INV-5), `client_invitation.renewed`, `client_access.granted` (F-03), `session.started`, `session.ended`, `session.refresh_reused`, `portal_preferences.updated`, `portal_branding.updated`. An email that matches no contact writes no audit event (there is no subject); a security metric with a hashed fingerprint is kept instead.

Outbox events (P-08 §4.5; identifiers and enums only, never an email, code, token or IP): `portal.sign_in_code_requested` {challenge_id, contact_id}, `portal.link_renew_requested` {secure_link_id}, `contact.portal_state_changed` {contact_id, state}; consumed: `access.changed`, `client_access.revoked` (end portal sessions, revoke trusted devices).

## 8. Example payloads
Brightwater Hale, synthetic (POR-01, POR-02 screen contracts; P-08-T08 writes the seed rows).

`GET /v1/portal/home?scope_id=…` (Claire Feld, POR-02 a), abridged:
```json
{
  "scope": {"kind": "client", "id": "…", "label": "Jonah & Claire Feld", "sub": "Household · Brooklyn, NY", "role_label": "Taxpayer"},
  "todos": [
    {"kind": "upload", "count": 2, "state": "open", "detail": "Form 1095-C and your 2025 estimated payment confirmations", "target": {"screen": "POR-03", "params": {}}},
    {"kind": "answer", "count": 3, "state": "open", "facts": {"organizer_count": 2, "from_team_count": 1}, "target": {"screen": "POR-05", "params": {}}},
    {"kind": "sign", "count": 0, "state": "none"},
    {"kind": "deliverables", "count": 2, "state": "open", "target": {"screen": "POR-09", "params": {}}}
  ],
  "work_cards": [{
    "work_item_id": "…", "kind": "tax_return", "title": "2025 Tax Return · Form 1040", "sub": "Extended to Oct 15, 2026",
    "pill": {"code": "reviewing_return", "variant": "state"},
    "stages": [{"code": "gather_documents", "state": "done"}, {"code": "prepare", "state": "done"}, {"code": "review", "state": "current"}, {"code": "sign_form_8879", "state": "upcoming"}, {"code": "file", "state": "upcoming"}],
    "note_code": "waiting_on_k1", "note_subject": "Ridgeline Property Partners, LP", "note_date": "2026-09-15"
  }],
  "binder": {"binder_id": "…", "done": 19, "total": 21, "sorted_count": 37},
  "team": [{"user_id": "…", "display_name": "Daniel Reyes", "role_code": "partner_signs_return"}, {"user_id": "…", "display_name": "Kevin Osei", "role_code": "preparer_day_to_day"}],
  "earlier": [{"kind": "return_filed", "facts": {"tax_year": 2024, "form": "1040"}}],
  "my_k1s": [], "recent_threads": [], "notices_info": [],
  "first_visit": false, "welcome_dismissed": true, "all_done": false
}
```

`GET /v1/portal/home` for Sam Ortiz (third party only): `404`. `PUT /v1/portal/preferences` `{"scope_id": "…", "welcome_dismissed": true, "version": 0}` → `{"scope_id": "…", "welcome_dismissed": true, "welcome_dismissed_at": "2026-02-02T15:04:00Z", "version": 1}`; replayed with `version: 0` → `409 {"detail": "portal_preferences_stale"}`.

`POST /v1/clients/{client_id}/contacts/{contact_id}/portal-unlock` (Grace Holloway, Claire Feld locked) → `{"client_id": "…", "contact_id": "…", "portal_status": "active", "locked_until": null}`.

`GET /v1/me` (Tess Moreno), the new fields: `"portal": {"shell": "full", "scopes": [{"kind": "client_entity", "id": "…", "label": "Copperleaf Coffee Roasters, Inc.", "role_label": "Owner"}], "nav": ["home", "documents", "questions", "approvals", "sign", "messages", "deliverables"], "landing": "home"}, "mfa": {"enrolled": true, "required": true, "trusted_until": null}`.

Not served yet: `POST /v1/portal/auth/start {"email": "claire.feld@gmail.com"}` and the same call for an unknown email → `202 {"challenge_id": "…", "code_expires_at": "2026-09-14T14:32:00Z", "resend_available_at": "2026-09-14T14:22:42Z"}`.

## 9. Consumer contract tests
- Provider stub test: `backend/tests/contracts/c5_portal/test_c5_portal_stub.py` (every served route and action, the Idempotency-Key, classification of every model including the unserved shapes, Public-only branding, agent and system denies, flag off 404 / on 501, `/v1/me` optional fields, the pre-session family unserved; SPEC-320 AC-1 to AC-5).
- Consumer tests (P-08-T02): `backend/tests/contracts/c5_portal/` plus TypeScript fixture assertions in `apps/web/src/fixtures/contracts/portal.contract.test.ts` (no-enumeration shape, `tries_left` and `locked_until` facts, the home DTO without firm status codes, amounts or agent fields, Public-only branding). They run in the provider's CI.

## 10. Versioning
Additive to C5 v1 in place (v1.1). Breaking changes ship as v2 with one sprint of overlap (see `docs/contracts/README.md`).

| Version | Frozen on | Overlap ends | Notes |
|---|---|---|---|
| v1.1 | (planned 2026-12-11, with C5) | | stub 2026-10-23 (P-08-T01): home, preferences, unlock, MFA reset, `/v1/me` portal and mfa; the pre-session family and branding specified, served by T05, T10, T17, T18, T21 after DEC-139's decision |

## 11. Open points
- **DEC-139:** the pre-session family and `/branding/logo` need an ADR extending ADR-152's public-route list before P-08-T05 and T10 merge (P-08 OQ-2); the action spelling; the DTO fields added beyond the plan.
- P-08 OQ-1: who may reset MFA (security admin with fresh MFA is the stub's cell; confirm before T21).
- P-08 OQ-5: "Your day-to-day contact" per work-item kind, decided before T13.
