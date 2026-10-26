---
id: RB-35
title: A client is locked out of portal sign-in or two-step
owner: builder
alarms: []
last_rehearsed: never
rehearse_by: 2027-03-16
---
# RB-35 · A client is locked out of portal sign-in or two-step

| Field | Value |
|---|---|
| Owner | builder (the firm's own people run the unlock; this runbook is for when they cannot, or when lockouts spread) |
| Severity range | SEV4 (one person) to SEV2 (a wave of lockouts on one firm or many) |
| Linked from | RB-22 (identity outage: the portal half); POR-01g's "contact ‹person›" |
| SLO affected | SLO-01 (sign-in errors) when a wave |
| Kill switches that apply | the per-firm `portal_sign_in` control (RB-36) if the lockouts are an attack |
| Rehearse by | before both portal flags retire (P-08-T28, Tue Mar 16, 2027) |
| Last rehearsed | never |
| Last reviewed against an incident | never |

Written for P-08-T28 (P-08 §5, §7; C5 v1.1 portal half, `docs/contracts/portal-identity.md`; DEC-212, DEC-250, DEC-329). Portal sign-in is an emailed 6-digit code (10 minutes). The **third wrong code** locks that email on that host for **15 minutes** (POR-01g: "sign-in is paused for 15 minutes", naming the firm's support contact). A person the MFA floor covers (owners, signers, approvers) also passes a TOTP second step; repeated wrong second-step codes answer 423 `mfa_locked`. An unknown address sees exactly the same screens and lock, and no email is sent.

## 1. Recognise it
- A client calls the firm: "Too many attempts" (POR-01g), or a second-step `mfa_locked`, or a lost authenticator.
- `portal_sign_in.locked` or `portal_mfa.locked` audit events for a firm rise above its usual handful in an hour (identifiers only; read as the database owner, read-only, through an ops task).

Check first: is it one person (an unlock) or many people on one firm or every firm (an attack or a broken code email, go to section 4)?

## 2. Contain
One person, sign-in lock: wait 15 minutes, or a firm person with `contact.unlock` (firm admin, security admin, engagement partner, manager, client service) unlocks from the client's contacts (CLI-04): `POST /v1/clients/{client_id}/contacts/{contact_id}/portal-unlock`. The unlock is audited as `contact.unlocked`, naming who did it. The agent principal is denied.

One person, lost or locked second step: a **security admin** with fresh two-step resets it from CLI-04 or ADM-06: `POST /v1/clients/{client_id}/contacts/{contact_id}/mfa-reset` with an `Idempotency-Key`. The client enrols again at the next sign-in. Confirm who is asking before a reset: call the client on a number the firm already has, never one given in the request.

A wave on one firm: pause that firm's portal sign-in (RB-36) while you assess. Sessions already open carry on.

## 3. Preserve
The audit events (`portal_sign_in.failed`, `.locked`, `portal_mfa.failed`, `.locked`, `contact.unlocked`, `portal_mfa.reset`) with their ids and timestamps, and the security metric's hashed fingerprints for unknown addresses. Never copy an email address, a code or a device cookie into a ticket; refer to contacts by id.

## 4. Assess
- One person who mistyped: done after the unlock.
- Many addresses, many unknown, one host: credential stuffing (INC-2026-005's shape). Keep the pause, check the WAF rate rule on the portal distribution (`infra/modules/waf`), and open an incident.
- Codes not arriving, so people retry and lock: the code email is failing. Go to RB-20 (deliverability); unlocks will not help until mail flows.
- Second-step failures for many people at once: the identity provider's TOTP is failing. Go to RB-22.

## 5. Notify
One person: the firm person who unlocked tells the client. A wave: tell the firm's admins in-app; if client data may have been reached by someone else, RB-08 and RB-27 decide the notices.

## 6. Recover
Unlock or reset per section 2; resume sign-in (RB-36 section 6) once the cause is fixed.

## 7. Verify
The person signs in end to end on their firm's host (and passes the second step if covered); the audit trail shows the unlock or reset with the person who did it.

## 8. Review
Blameless review for a wave (ADR-097). A lock that a real person hit repeatedly may mean POR-01's copy or the resend countdown needs a change: route it to the Pilot 0 usability log (P-08-T29).

## Rehearsal log
| Date | Kind (drill, staging walk-through, tabletop) | Result | Changes made |
|---|---|---|---|
