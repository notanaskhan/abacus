---
id: TASK-030
title: Client invitations and client users
spec: SPEC-015
acceptance_criteria: [AC-1, AC-2, AC-3, AC-4, AC-5, AC-6, AC-7, AC-8, AC-9, AC-10]
risk_zone: red
status: done
branch: task-030-client-invitations
worktree:
created: 2026-10-08
updated: 2026-10-08
---

> **Rules for the agent working this task**
> - Read this whole file before doing anything. Continue from the *Handoff* section if it has content.
> - Load only the files listed under *Context to load*, plus what the plan requires.
> - Amber and red tasks: do not write code until the plan is marked approved.
> - If scope must change, **stop** and add it to *Questions for the human*.
> - Never mark `done` until every item in *Definition of done* passes.
> - Append to the *Progress log* before ending any session, even mid-task.

## Objective
Implement SPEC-015 (approved, Q1–Q5): client members as a separate kind, invitations with single-use tokens delivered by email, acceptance by a passwordlessly signed-in identity, contact management, and client contexts governed by the matrix's client rows.

## Scope
All of SPEC-015. Excluded: the client SPA route tree, SES, and bulk import.

## Context to load
- Spec: `docs/specs/SPEC-015-client-invitations.md`
- ADRs: ADR-029, ADR-030, ADR-020, ADR-106, ADR-065
- Code:
  - `identity` (`service.sign_in`, `choose_tenant`, `tokens`, `repository`, routing markers);
  - `communications` (`service.send`, `messages`);
  - migrations 0001, 0005 and 0006 (`users`, `memberships`, `engagement_members`)

## Plan
- [x] Plan approved by human (founder, 2026-10-08: D1–D6). Approved by founder: paths listed under *Protected paths*

### Design (for founder review)
1. **The token is never at rest (D1):**
   - creating an invitation stores no token, and the outbox event `client_invitation.created` carries only the invitation ID;
   - communications' handler calls `identity.api.issue_invitation_token(tenant, invitation_id)`, which generates 32 random bytes, stores the SHA-256 and returns the token once;
   - the handler then renders and sends the email;
   - a resend reissues the token, so the old hash is replaced.
2. **Acceptance runs without a membership (D2):**
   - `POST /v1/invitations/accept` uses a new dependency `current_identity`: a verified firm-issuer token whose claims carry a verified email (`email`, `email_verified`; `VerifiedIdentity` gains `email`). It needs no user record and no membership, and uses the route marker `SELF`.
   - `accept_client_invitation(identity, token)` takes these steps:
     1. finds the invitation by hash through the SECURITY DEFINER `client_invitation_by_hash(hash)` (pending and unexpired, returning the tenant, ID, email, engagement and role);
     2. checks the email (case-insensitive);
     3. calls `provision_client_user(issuer, subject, email, display_name)` (definer: upsert by issuer and subject);
     4. refuses if the user already has a **staff** membership in that firm (Q5);
     5. in one unit of work in the firm's tenant (actor `system`, `invitation:<id>`): `add_client_membership(user)` (definer, kind `client`, no firm role, from the session's tenant), the engagement role, the invitation accepted, and the audit event.

   Every failure returns the same 404.
3. **No app writes to `users` or `memberships` (D3):** creating a user and a client membership happens only through the two definer functions, both reviewed in `schema_check`, so the app role can never create a staff membership.
4. **Kind separation:**
   - `memberships.kind` (`staff` or `client`) with a CHECK (client means no firm role);
   - a trigger on `engagement_members` checks that the role's kind matches the membership's kind (client roles for client memberships, staff roles for staff);
   - the role CHECK is extended with the client roles, and `EngagementRole` gains them (as `ClientRole`).
5. **Emails (D4):**
   - communications gains a `Transport` protocol and `LocalMailbox` (synthetic environments only: JSON files in `local_mailbox_dir`, default `backend/.local/mailbox`);
   - system emails go through `deliver_template(tenant, kind, to, params)`, a fixed template rendered and checked by the scope checker;
   - the message is recorded in `messages` with the link redacted, so the token is never stored;
   - `messages.created_by` is the inviter.
6. **Rate limits (D5):**
   - failed acceptances go in `invitation_failures(identity_hash, failed_at)`, a non-tenant table reached only through the definer functions;
   - 10 failures per hour lock the identity for 15 minutes;
   - invitations per engagement per day (50) are counted from `client_invitations`.
7. **Routes and service** (identity, beside the team functions, with a slot for the engagement check): invite, list contacts, revoke, resend, remove member, as in SPEC-015 §8, with the matrix actions `client_contact.invite`, `client_contact.read` and `client_contact.remove` (client admins limited to contributors in the service).
8. **Client contexts:** `choose_tenant` builds them as today (`firm_role=None`). `MembershipRecord` carries the kind, and `AuthContext` exposes `is_client` for the SPA's `/v1/me`.
9. **Migration 0025:**
   - the membership kind;
   - the engagement member roles and the trigger;
   - `client_invitations` and `invitation_failures`;
   - the three definer functions;
   - schema maps and the matrix codegen.

**Protected paths (approval file):**
- `backend/src/abacus/modules/{identity,communications,engagements}/**`;
- `backend/migrations/**`, `backend/src/abacus/kernel/config.py`;
- `docs/architecture/permission-matrix.yaml`;
- `backend/src/abacus_tools/**`, `backend/tests/unit/**`, `backend/src/abacus/api/**`, `backend/src/abacus/worker/**`.

### Questions for approval
- **D1. The token is generated at delivery time and only its hash is stored, so it never appears in the outbox, a message body or the database?** *Recommendation: yes.*
- **D2. Acceptance uses a verified identity (with a verified email claim) without needing an existing user or membership?** *Recommendation: yes.* It's the only route that does.
- **D3. Users and client memberships are created only through reviewed SECURITY DEFINER functions, so the app role never gets INSERT on `users` or `memberships`?** *Recommendation: yes.*
- **D4. Invitation emails go through a new fixed-template path in communications (scope-checked, recorded with the link redacted) and a local mailbox transport until SES?** *Recommendation: yes.*
- **D5. Failed acceptances are counted in a small non-tenant table reached only through the definer functions?** *Recommendation: yes.* The tenant is unknown when a token is wrong.
- **D6. Write the approval file for the protected paths above?** *Recommendation: yes.*

## Definition of done
- [ ] All listed ACs have passing tests that reference them (independent tests deferred by the founder)
- [ ] Type check, lint, format, architecture and dependency rules pass
- [ ] Every query is tenant-scoped; every endpoint checks authorisation
- [ ] Module READMEs and the relevant docs are updated

## Progress log
- `2026-10-08` — Implemented:
  - migration 0025 (membership kind, client roles and the kind trigger, `client_invitations`, `invitation_tokens`, `invitation_failures`, five definer functions);
  - identity invitations (create, revoke, resend, remove, contacts, issue token, accept);
  - the `IDENTITY` route marker and `current_identity`;
  - the verified email claim;
  - the membership kind on `/v1/me`;
  - engagement contact routes;
  - the communications transport (local mailbox) and invitation delivery;
  - the matrix actions, schema maps and pins.

  Unit tests (8,903) and gates pass. An end-to-end run against local Postgres passed: invite, email to the mailbox, resend kills the old link, wrong email refused, accept once, replay refused, client authorised by client rows and refused firm actions, removal effective.
- `2026-10-08` — SPEC-015 approved and merged (#54). Design written for founder review.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| The invitation email isn't run through the scope checker | It's a fixed template with only the link and a date; nothing client-specific to check | No |
| Each acceptance attempt is audited in the platform (nil) tenant, because the unit of work needs an event to commit the failure counter | Security attempts are worth a trail; the firm is unknown until the token matches | No |
| The link carries the token in the URL fragment (`#token=`) | Fragments aren't sent to servers or logged by proxies | No |

## Questions for the human
- Design questions D1–D6 (above).

## Handoff
