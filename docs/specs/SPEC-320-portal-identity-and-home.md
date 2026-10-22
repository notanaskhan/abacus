---
id: SPEC-320
title: "Portal identity and home (C5 v1.1, portal half): passwordless sign-in without enumeration, lockout, two-step for the DEC-34 floor, invitations v2, link renewal, firm-side recovery, the POR-02 home read model and preferences - outline"
status: draft
owner: notanaskhan
risk_zone: red
related_adrs: [ADR-005, ADR-031, ADR-139, ADR-146, ADR-152, ADR-163]
related_specs: [SPEC-015, SPEC-020, SPEC-042, SPEC-319]
created: 2026-10-23
updated: 2026-10-23
---

> **Outline.** Written with the C5 v1.1 portal-half stub (P-08-T01, TASK-431). The epic is the
> source until this spec is final: `docs/plan/epics/P-08.md` §3 (stories), §4 (backend), §8 (C5).
> The contract is `docs/contracts/portal-identity.md`. AC-1 to AC-5 hold for the stub; AC-6 onward
> are the behaviour the implementing tasks prove (P-08-T20 and T24 write the independent suites).
>
> **Supersedes SPEC-015's expiry and lockout clauses (DEC-35).** SPEC-015 §5 and Q3 set a client
> invitation to expire after 7 days and say nothing of sign-in codes or locks. From this spec on:
> invitation and reminder links expire after **14 days**, single use; a sign-in code expires after
> **10 minutes**; **3** wrong codes for one email (across resends) lock sign-in for **15 minutes**,
> lifted by waiting or by a firm unlock; trusted devices last **30 days** at most (a firm may set
> fewer). SPEC-015's other clauses (one 404 for every bad token, hashed single-use tokens, the
> daily invitation limit) stand. Existing pending invitations keep the expiry they were issued with.

## 1. Summary
A client signs in to the firm's portal with an emailed 6-digit code and no password; sign-in never reveals whether an email has an account. Owners, signers and approvers confirm a second step with an authenticator (DEC-34). An invited person sees exactly what the firm asks of them before accepting. An expired link can be renewed to the address it was sent to. The home shows one scope's to-dos, work stages, binder progress and team in client words, never a firm status, an amount or the agent. A named firm person can unlock a locked contact or reset a lost second step; the agent never can (INV-1).

## 2. Problem and context
Today the portal uses the hosted OIDC client sign-in (`ClientAccept.tsx`) and a legacy home. POR-01 and POR-02 need an in-product sign-in through a BFF session (ADR P-54), the MFA floor, invitations v2 and a role-union home (DEC-129) on the firm's host (ADR-163). R-01, P-07 and G-02 build on the same contract; C5 freezes S3 (Fri Dec 11, 2026).

## 3. Actors
| Actor | Role in this feature |
|---|---|
| Client person (taxpayer, owner, contributor, delegate, third party, K-1 recipient) | Signs in, verifies a second step when the floor requires it, accepts an invitation, renews a link, reads the home, dismisses the welcome |
| Firm admin, engagement partner, manager, `client_service` | Unlock a contact's sign-in |
| Security admin (fresh MFA) | Unlock; reset a contact's second step |
| Agent, system | Denied every action here |

## 4. Goals and non-goals
**Goals:** the C5 v1.1 portal-half routes, models and matrix rows (contract §2, §3); flags `portal.sign_in_v2` and `portal.home_v2`.

**Non-goals:** the portal screens beyond POR-01 and POR-02 (R-01 and later); ADM-06 MFA policy screens (G-02); custom domains (P1); the TRI MFA predicate (T-01 registers it).

## 5. User stories and acceptance criteria
### Story 1: the C5 v1.1 portal-half stub (P-08-T01)
- **AC-1** Every served route in the contract §2.1 exists with exactly one matrix action and documents 404 and 501; preferences documents 409; the MFA reset requires an `Idempotency-Key` header.
- **AC-2** Every field of every portal-half model, served or not, carries a classification tag (ADR-031); branding fields are all Public and none names a tenant; the contact's portal status is C2's generated `InvitationStatus`.
- **AC-3** `contact.unlock`, `contact.mfa_reset`, `portal_home.read` and `portal_preferences.update` deny the agent and the system principal; the two portal actions grant no firm role; the home is `scope_only`; the MFA reset is security admin only with fresh MFA.
- **AC-4** With `portal.home_v2` off the home and preferences answer 404, with `portal.sign_in_v2` off the unlock and MFA reset answer 404; with the flag on a stubbed route answers 501 `not_implemented`. Both flags are boolean and default off.
- **AC-5** `/v1/me` gains only optional `portal` and `mfa` fields; the pre-session family and branding are not served until their public-route decision lands (DEC-139).

### Story 2: passwordless sign-in without enumeration (P-08-T10; epic Stories 2.1 to 2.3)
- **AC-6** `start` answers 202 with one shape and padded timing for any email (unknown, staff, no active grant, another firm's, locked); a code email is sent only to an eligible contact; no tenant audit event names a person who does not exist.
- **AC-7** A wrong code answers 401 `code_mismatch {tries_left}`; the third wrong code for the email in the window answers 423 `sign_in_locked {locked_until}` 15 minutes ahead on `kernel.clock`, for an email that matches no one too; a resend voids the old code and does not reset the tries; a code older than 10 minutes answers 410 `code_expired`.
- **AC-8** Successful verification lands by role union: full shell → home; third party only → requests; K-1 only → K-1s; TCWG → governance; prospect → intake; component auditor → component room.
- **AC-9** A portal session is pinned to the tenant and host it was minted on; on another host it is answered as no session (401), and a staff session on a portal host is refused the same way (ADR-163 §5).

### Story 3: two-step for the floor (P-08-T17; epic Stories 3.1 to 3.4)
- **AC-10** An active `owner` grant or an `approver_of_record`, `signing_officer` or `ske_designee` designation requires the second step; a predicate that raises or times out requires it (fail closed); the firm may widen the floor to every client user, never narrow it.
- **AC-11** Setup returns the QR URI and manual key, verifies a first code and returns 8 backup codes once; a backup code verifies once; three wrong second-step codes lock for 15 minutes (423 `mfa_locked`); a trusted device lasts at most 30 days and is revoked with the person's access.

### Story 4: invitations and links (P-08-T18, T21; epic Stories 4.1, 5.1)
- **AC-12** Preview returns the firm, organisation, invitee, access summary, terms and expiry; an expired (over 14 days), used, revoked, malformed or staff token answers the same 404.
- **AC-13** Accept with the terms version creates the template's grants in one unit of work, attributed to the inviter (INV-5).
- **AC-14** Renew answers 202 for any token and sends a new link only to the address the original was sent to; an invitation renews at most twice; a revoked one never.

### Story 5: home and preferences (P-08-T12, T13; epic Stories 6.1 to 6.7)
- **AC-15** The home for a covered full-client scope composes to-dos, work cards with client stage codes, binder progress (firm-attributed sorted count), team with client-facing role codes and Earlier rows; Claire Feld's E0 home reads Upload 2 and binder 19 of 21 with 37 sorted.
- **AC-16** No home field carries a firm status code, an amount, materiality, an agent name or a confidence; every aggregate is filtered by the grant that covers its own target scope (INV-4); a scope no grant covers, or a person with no full-client grant, answers 404.
- **AC-17** Dismissing the welcome persists per user and scope with a version (409 `portal_preferences_stale` on mismatch) and audits `portal_preferences.updated`.

### Story 6: firm-side recovery (P-08-T21; epic Stories 7.1 to 7.3)
- **AC-18** Unlock clears the lock and audits `portal.sign_in.unlocked` naming the person; a walled staff member gets 404 (INV-3).
- **AC-19** MFA reset removes the factor, backup codes and trusted devices, emails the client in the firm's name and sends the next sign-in to setup; audited as `portal.mfa.reset`.
- **AC-20** The per-firm sign-in pause answers 503 `sign_in_paused` for `start` and `verify` within 10 seconds; existing sessions are unaffected.

## 6. Behaviour and flows
**State transitions (contact `portal_state`, `invitation` words)**
| From | Event | To | Who can trigger |
|---|---|---|---|
| `not_invited` | invitation sent | `invited` | `client_contact.invite` (human) |
| `invited` | invitation accepted | `active` | the invitee |
| `active` | third wrong code or second-step code | `locked` | the system, on the client's attempts |
| `locked` | `locked_until` passes | `active` | the clock |
| `locked` | unlock | `active` | `contact.unlock` (human) |

## 7. Domain and data changes
None in the stub. P-08-T05 adds `portal_branding`, `portal_domains`, `portal_preferences` and `portal_resolve_host`; T10 `sign_in_challenges` and the `auth_sessions` surface columns; T17 `trusted_devices`, `mfa_backup_codes`, `portal_security_policies`; T18 the `client_invitations` v2 columns; T21 `secure_links` (P-08 §4.2).

## 8. Interfaces
The routes, models and actions are listed in `docs/contracts/portal-identity.md` §2 and §3 (code: `backend/src/abacus/modules/portal/contract.py`, `backend/src/abacus/modules/identity/portal_contract.py`).

## 9. Authorisation and tenancy
- **Tenant scoping:** `tenant_session(ctx)` on every read and write; home sources through `visible()` with `portal_scope` (F-03-T27). The host chooses branding only, never the tenant (ADR-163 §5).
- **Who can do what:** `docs/architecture/permission-matrix/portal.yaml` and `identity.yaml` (contract §2).
- **Ethical walls:** walled clients and contacts answer 404 to staff (INV-3).
- **Client-side access:** grants and role union (ADR-146, DEC-129); `scope_only` per target scope (INV-4).

## 10. AI behaviour
N/A: no model call. The agent is never named on the portal; files it sorted are attributed to the firm (DEC-19, INV-5).

## 11. Integrations
WorkOS for the user, the Magic Auth code and TOTP factors (P-08-T06 port, F-04 fake); SES for the firm-branded code, renewal and MFA-reset email through C16 templates (database content).

## 12. Edge cases and failure modes
- Start for a locked email: the same 202; verify answers 423 until `locked_until`.
- Resend racing verify: the first commit wins; the voided code answers `code_mismatch`.
- Unknown portal host: branding returns neutral values, the same shape.
- A predicate in the MFA floor times out: the second step is required.

## 13. Security and privacy
- **Data classification:** codes, tokens, TOTP secrets and backup codes Restricted (never logged, never stored in clear, never in a list payload); email addresses and names confidential; branding Public.
- **Threats considered:** account enumeration (one shape and timing), code guessing (3 tries and a lock), session replay across firms (host pinning), the agent reaching recovery (INV-1), white-label leaks (no "Accrued" in any payload).

## 14. Audit trail and evidence integrity
The audit events in the contract doc §7, identifiers only, with IP, device and session captured (DEC-60); the human actor on unlock and reset (INV-5).

## 15. Observability
Metrics: start, verify, lock and resend counts; a hashed-fingerprint security metric for emails that match no one; never an email, code, token or IP in logs.

## 16. Performance and scale
`start` and `verify` p95 ≤ 400 ms server time excluding email; code email send-start p95 ≤ 5 s; `GET /v1/portal/home` p95 ≤ 300 ms for one scope with ≤ 50 work items; branding cached at the edge 60 s by host (P-08 §4.3).

## 17. UX
POR-01 and POR-02 screen contracts (`docs/screens/`); flag off shows the legacy paths.

## 18. Test plan
| AC | Test type | Description |
|---|---|---|
| AC-1 to AC-5 | unit (contract) | `backend/tests/contracts/c5_portal/test_c5_portal_stub.py` |
| AC-6, AC-7, AC-15, AC-16 (shapes) | contract (consumer) | P-08-T02 in `backend/tests/contracts/c5_portal/` and `apps/web/src/fixtures/contracts/portal.contract.test.ts` |
| AC-6 to AC-14, AC-18 to AC-20 | integration | P-08-T20 and T24 (independent suites) |
| AC-15 to AC-17 | integration | P-08-T22 |

## 19. Rollout
- **Feature flags:** `portal.sign_in_v2` and `portal.home_v2` (default off, expire 2027-01-21; renewal or retirement with the legacy paths in P-08-T28).
- **Rollback:** the stub only adds routes behind the flags, optional `/v1/me` fields and matrix rows; revert the commit.

## 20. Open questions
- [ ] OQ-2: an ADR extending ADR-152's public-route list to the logo and the pre-session family (DEC-139), before P-08-T05 and T10 merge.
- [ ] OQ-1: MFA reset by security admin only (the stub's cell), confirmed before T21.
- [ ] OQ-5: the day-to-day contact per work-item kind, before T13.

## 21. Future / explicitly deferred
Custom portal domains (P1), the TRI MFA predicate (T-01), ADM-06 policy screens (G-02), the My K-1s, messages and notices home sources (T-02, N-03, N-04).
