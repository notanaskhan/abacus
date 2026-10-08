---
id: SPEC-015
title: Client invitations and client users
status: approved
owner: founder
risk_zone: red
related_adrs: [ADR-029, ADR-030, ADR-024, ADR-014, ADR-020, ADR-065, ADR-011]
related_specs: [SPEC-002, SPEC-006, SPEC-013]
created: 2026-10-08
updated: 2026-10-08
---

> **Instructions for coding agents**
> - Implement only what this spec describes. Anything not listed here is out of scope.
> - If anything is ambiguous or contradicts an ADR, **stop** and add it to *Open questions*. Do not guess.
> - Every test must reference the acceptance criterion (AC-n) it proves.
> - This spec must be `approved` with no open questions before implementation starts.

## 1. Summary
The client side of an engagement (the people at the audited company) gets accounts. This covers:
- **Invitations:** a firm's engagement partner or manager invites a client contact by email to one engagement, as `client_admin` or `client_contributor`. A client admin may invite contributors to the same engagement (Q2).
- **Delivery:** the invitation is a single-use, expiring link, delivered through the communications module's transport (a local mailbox now, SES with TASK-014).
- **Acceptance:** the client signs in passwordlessly (ADR-030, through the identity vendor) and accepts. That creates their client membership in the firm and their engagement role.
- **What client users can do:** client users are a distinct kind of member. They hold no firm role and see only the engagements they belong to, through the matrix's existing client rows. Access ends on the next request when revoked.

The client view shell (SPA route tree) is a separate UI task. This spec is the backend.

## 2. Problem and context
- **The roles already exist:** the matrix defines `client_admin` and `client_contributor` (request items marked client-visible, uploads, connections).
- **But no client can exist today:**
  - memberships are firm staff only;
  - `engagement_members.role` allows staff roles only;
  - there is no way to invite anyone.
- **Phase 2 needs this:** increment 2 (the client portal and connection flow) depends on it.

## 3. Actors
| Actor | Role in this feature |
|---|---|
| Engagement partners and managers | Invite and revoke client contacts on their engagements |
| Client admins | Invite and revoke contributors on their own engagement (Q2) |
| Client contacts | Accept by email link and sign in passwordlessly |
| The communications module | Delivers the invitation email (a guarded outbound message) |

## 4. Goals and non-goals
**Goals**
- **The member kind:** `memberships.kind` is `staff` or `client`. Client memberships can never hold a firm role (a database CHECK). `engagement_members.role` gains `client_admin` and `client_contributor`, allowed only for client memberships, and staff can't hold client roles (a CHECK through the membership).
- **Invitations:**
  - `client_invitations` (tenant-scoped) records the email (confidential), engagement, role, inviter, a token hash (SHA-256 of 32 random bytes), status (`pending`, `accepted`, `revoked`, `expired`), `expires_at` (7 days, Q3) and `accepted_by`;
  - the token itself is never stored or logged, and appears only in the link.
- **Delivery (Q1):**
  - creating an invitation emits `client_invitation.created`; the communications module renders a fixed template and sends it through its transport;
  - locally the transport is a file mailbox (`backend/.local/mailbox/`), and SES comes with TASK-014;
  - the API never returns the link.
- **Acceptance:** `POST /v1/invitations/accept {token}`, for a signed-in identity with no tenant needed.
  1. The token must match a pending, unexpired invitation.
  2. The identity's verified email must equal the invited email (case-insensitive).
  3. Then, in one unit of work: create the user if new, create (or reuse) the client membership in the firm, add the engagement role, mark the invitation accepted, and audit it.
- **Client contexts:** a client member's request context is an `AuthContext` with `firm_role=None`, and the matrix's client rows govern every action. Firm-only routes refuse client contexts (the matrix has no client grants on them). SPEC-014's firm-level reads don't apply to client roles, since no firm-level read grants them.
- **Management:**
  - list an engagement's client contacts and pending invitations;
  - revoke an invitation;
  - remove a client member from an engagement, which ends access on the next request;
  - resend, which issues a new token and invalidates the old one.

**Non-goals**
- **The client SPA route tree and branded invitation page:** a UI task and increment 2.
- **Client-side MFA enrolment:** optional per ADR-030, and the vendor's.
- **Bulk import of client contacts.**
- **Email transport configuration:** TASK-014.

## 5. User stories and acceptance criteria
### Story 1: The firm brings the client in
- **AC-1** Given an engagement partner or manager, when they invite an email as `client_admin` (or `client_contributor`), then a pending invitation is stored (token hashed), `client_invitation.created` is audited and emitted, and the email is delivered through communications with the link. The API response carries the invitation's ID, email and status, never the link.
- **AC-2** Given a client admin on an engagement, when they invite an email as `client_contributor` to that engagement, then it works as in AC-1. Inviting as `client_admin`, or to another engagement, is refused (Q2).
- **AC-3** Given an engagement that is archived, or an invitation limit reached (Q4), then the invitation is refused (409).

### Story 2: The client gets in, once
- **AC-4** Given a valid pending invitation, when the invited person signs in passwordlessly and accepts with the token, then in one unit of work:
  - the user exists;
  - the client membership exists (reused if they're already a client of the firm);
  - the engagement role is added;
  - the invitation is `accepted`;
  - `client_invitation.accepted` is audited.
- **AC-5** Given a token that is wrong, expired, revoked or already used, or a signed-in email that differs from the invited one, then acceptance is refused with the same 404 in every case (no oracle). Failed attempts are rate-limited per identity (Q4).
- **AC-6** Given a staff member of the firm accepting a client invitation, then it is refused. One person can't be both staff and client in the same firm (Q5).

### Story 3: Clients see only their engagements
- **AC-7** Given a client member, when they call any route, then:
  - they are authorised only by the matrix's client rows on engagements where they hold a client role;
  - firm-level routes refuse them;
  - list queries (`visible()`) return only their engagements' rows.
- **AC-8** Given a client member removed from an engagement (or their membership revoked), then their next request on it is refused (ADR-030).

### Story 4: The firm stays in control
- **AC-9** Given an engagement partner or manager (or a client admin, for contributors), when they list contacts, then they see the client members and pending invitations of that engagement. They can revoke a pending invitation or remove a client member, and each is audited.
- **AC-10** Given a resend, then a new token is issued, the old one stops working, and a new email is sent.

## 6. Behaviour and flows
1. **Invite:** authorise `client_contact.invite`, validate, insert the invitation, audit, emit. Communications delivers the email.
2. **Accept:**
   1. the client clicks the link and the SPA's client route asks the vendor for a passwordless sign-in;
   2. the SPA posts the token with the session;
   3. the backend verifies the token and the email, and creates the membership and the role.
3. **Use:** later requests resolve the client membership as for staff (one active membership per firm), and `authorise` applies the client rows.

## 7. Domain and data changes
- **`memberships.kind`:** `staff` or `client`, default `staff`, with a CHECK that `kind = 'client'` implies `firm_role IS NULL`.
- **`engagement_members.role`** gains the client roles. A trigger (or an FK to a membership kind view) enforces that client roles belong to client memberships and staff roles to staff memberships.
- **`client_invitations`** as in §4, with forced RLS and UPDATE on status columns only, plus an index on (`tenant_id`, `engagement_id`).
- **New matrix actions** (a protected change):
  - `client_contact.invite`: engagement_partner and manager; `client_admin` only for contributors (Q2);
  - `client_contact.read`: engagement_partner, manager, senior and client_admin;
  - `client_contact.remove`: engagement_partner, manager, and client_admin (contributors only).
- **Communications:** an `invitation` channel template, and the local mailbox transport.

## 8. Interfaces
| Interface | Purpose |
|---|---|
| `POST /v1/engagements/{id}/client-invitations` `{email, role}` | Invite (AC-1 to AC-3) |
| `GET /v1/engagements/{id}/client-contacts` | Members and pending invitations (AC-9) |
| `POST /v1/engagements/{id}/client-invitations/{iid}/revoke` and `…/resend` | AC-9, AC-10 |
| `DELETE /v1/engagements/{id}/client-contacts/{user_id}` | Remove a client member (AC-8, AC-9) |
| `POST /v1/invitations/accept` `{token}` | Accept (AC-4 to AC-6), signed in with no tenant (route marker `SELF`) |

## 9. Authorisation and tenancy
- **Who can do what:** invitations and contacts are authorised per engagement by the new actions.
- **Accepting:** acceptance is the one route where a signed-in identity without a membership acts. It runs in the invitation's tenant, from the token's lookup through a SECURITY DEFINER function that returns only the invitation row for a matching hash.
- **Client contexts** never hold firm roles, support roles, or staff engagement roles.
- **Walls** don't apply to client users (walls separate firm staff from clients).

## 10. AI behaviour
None.

## 11. Integrations
- **The identity vendor's passwordless email login** (ADR-029, ADR-030). Locally, the fake OIDC server signs client tokens.
- **The email transport:** SES with TASK-014.

## 12. Edge cases and failure modes
- **Invited twice:** a pending invitation for the same email and engagement is replaced (the old token is invalidated).
- **An email changed at the vendor before accepting:** it no longer matches, so the invitation must be reissued.
- **A client of two firms:** two client memberships, chosen by the tenant header as for staff.
- **A delivery failure:** the invitation stays pending and the outbox retries. A resend is available.

## 13. Security and privacy
- **Tokens:** high-entropy, single-use, expiring, hashed at rest, never logged, never in API responses.
- **Binding:** acceptance is bound to the verified email, and responses are the same for every failure.
- **Classification:** emails are confidential and never logged.
- **Separation:** client and staff kinds are separated by database constraints.
- **The outbound email is a fixed template**, checked by the scope checker like any message (SPEC-006).

## 14. Audit trail and evidence integrity
- **Audited:** `client_invitation.created`, `client_invitation.accepted`, `client_invitation.revoked`, `client_invitation.resent` and `client_member.removed`.
- **Kept off the trail:** emails and tokens. Audit references hold fingerprints only.

## 15. Observability
- **Metrics:** invitations by outcome, acceptance latency, and rejected acceptances.
- **Logs:** identifiers only.

## 16. Performance and scale
Small volumes: tens of contacts per engagement.

## 17. UX
API only. The client route tree and invitation page are the next UI task.

## 18. Test plan
| AC | Test type | Description |
|---|---|---|
| AC-1 to AC-3 | integration | Invite, client-admin limits, archived engagement, the invitation limit, email delivered to the mailbox |
| AC-4 to AC-6 | integration | Accept once; every invalid case gives the same 404; staff refused; rate limit |
| AC-7, AC-8 | integration + generated matrix tests | Client contexts follow the client rows; firm routes refused; removal effective next request |
| AC-9, AC-10 | integration | List, revoke, remove, resend |

## 19. Rollout
Additive migrations. Existing memberships become `staff`.

## 20. Open questions
None. Answered by the founder on 2026-10-08 (all recommendations):
- [x] **Q1: delivery before SES.** *Recommendation:* communications gains a transport interface with a local file mailbox (and a test double). The API never returns the link. SES is configured in TASK-014.
- [x] **Q2: who invites whom.** *Recommendation:* engagement partners and managers invite client admins and contributors. Client admins invite contributors to their own engagement only.
- [x] **Q3: expiry.** *Recommendation:* 7 days, single-use, and a resend issues a new token.
- [x] **Q4: limits.** *Recommendation:* at most 50 invitations per engagement per day, and 10 failed acceptances per identity per hour, then 15 minutes refused.
- [x] **Q5: one person as staff and client of the same firm.** *Recommendation:* not allowed. A person is either staff or client within a firm, which keeps the separation simple and auditable. Across firms anything is allowed.

## 21. Future / explicitly deferred
- The client route tree and branded invitation page (UI and increment 2).
- Bulk contact import.
- Client-side session management UI.
- Delegated invitation approval.
