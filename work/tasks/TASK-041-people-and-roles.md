---
id: TASK-041
title: People and firm roles (SSO held)
spec: SPEC-024
acceptance_criteria: [AC-3, AC-4, AC-8]
risk_zone: red
status: done
branch: task-041-people-and-roles
worktree:
created: 2026-10-09
updated: 2026-10-09
---

> **Rules for the agent working this task**
> - Read this whole file before doing anything. Continue from the *Handoff* section if it has content.
> - Load only the files listed under *Context to load*, plus what the plan requires.
> - Amber and red tasks: do not write code until the plan is marked approved.
> - If scope must change, **stop** and add it to *Questions for the human*.
> - Never mark `done` until every item in *Definition of done* passes.
> - Append to the *Progress log* before ending any session, even mid-task.

## Objective
A firm administrator invites staff with a firm role, changes roles and revokes access, with the firm never left without an administrator.

**SSO (SPEC-024 AC-2) is held** until the founder confirms the identity vendor (TASK-040 amendment 4). It becomes its own task.

## Scope
SPEC-024 AC-3, AC-4 and AC-8 (for these screens).

## Context to load
- Spec: `docs/specs/SPEC-024-act-0-the-firm-gets-ready.md`; ADR-002, ADR-030
- Code:
  - the client-invitation pattern (migration 0025, `identity/invitations.py`, `communications/invitations.py`, `ClientAccept.tsx`);
  - migration 0027's team definer functions (last-partner protection as the pattern);
  - `identity.service` (`active_memberships`, `display_names`);
  - `AdminLayout`, `mfa`.

## Plan
- [x] Plan approved by human (founder, 2026-10-09: D1–D5). Approved by founder: paths listed under *Protected paths*

### What the code shows
- **The client invitation path is complete:** single-use expiring tokens issued at delivery and stored only as hashes, a lockout after failed acceptances, email delivery through communications, and the SPA's accept page.
- **It's tied to client roles and an engagement**, so staff need their own invitations.
- **The app can't change memberships:** it has no UPDATE grant on them. Role changes and revocation need reviewed definer functions, as team changes did (0027).
- **The local identity provider never sends MFA,** so every fresh-MFA action (walls, and now people) is refused locally.

### Design (for founder review)
1. **Staff invitations (migration 0033, D1):**
   - `staff_invitations`: tenant, email, firm role (`firm_admin`, `practice_leader`, `quality_partner` or none), invited by, status (`pending`, `accepted`, `revoked`, `expired`), expiry (14 days), accepted by and at;
   - forced RLS; one pending invitation per email per firm;
   - tokens in a separate `staff_invitation_tokens` table, reached only through new definer functions `staff_invitation_token_set` and `staff_invitation_token_find`, which reuse the lockout in `invitation_failures`.

   The client tables and functions stay as they are.
2. **Accepting:**
   - `POST /v1/invitations/staff/accept` (`IDENTITY`, token);
   - the provider-verified email must match the invitation;
   - `provision_client_user` (which creates a user generally, despite its name) and a new definer `add_staff_membership(user, role)`, which refuses someone who's a client contact of that firm (never staff and client of one firm, SPEC-015 Q5) and reactivates a revoked staff membership with the new role;
   - audited `staff_invitation.accepted`.
   - **The SPA page `/join`:** the token moves out of the address bar into this tab's storage (as SPEC-015 does), sign-in, accept, then the workspace with that firm chosen.
3. **Roles and revocation (definer functions in the session's firm, D2):**
   - `membership_set_firm_role(user, role)` and `membership_revoke(user)`, both returning `ok`, `not_found` or `last_admin`;
   - the firm always keeps at least one active firm administrator (AC-4);
   - revocation applies on the next request (memberships are read fresh), and the person's engagement roles stay as history (they can't act without a membership).
4. **Service and routes** (`identity/staff.py`, all `firm.manage_users`, fresh MFA except listing):
   - `GET /v1/firm/staff`: active and revoked members (name, email, firm role, status), plus pending invitations;
   - `POST /v1/firm/staff/invitations`;
   - `POST …/invitations/{id}/resend` and `…/revoke`;
   - `PUT /v1/firm/staff/{user_id}/role`;
   - `POST /v1/firm/staff/{user_id}/revoke`.

   Each is audited, and the invitation emits `StaffInvitationIssued`, which communications delivers with a `/join#token=…` link.
5. **Web:** a "People" tab in Firm admin (firm admins only):
   - the staff table, with a role select and Revoke (confirmed);
   - pending invitations, with Resend and Revoke;
   - an Invite form (email and firm role);
   - a 403 opens "Confirm it's you";
   - a refusal for the last admin says why.
6. **Local MFA (D3):** the local provider marks its tokens as signed in with MFA at that moment. Fresh-MFA screens (walls, people) can then be tried locally, and "Confirm it's you" still shows once the token is more than 15 minutes old.

**Protected paths (approval file):**
- `backend/src/abacus/modules/identity/*` (top-level files only; `identity/authz` untouched, as in TASK-040);
- `backend/src/abacus_tools/quality/schema_check.py` (the new tables and definer functions);
- `backend/src/abacus_tools/quality/banned_patterns.py` (if the staff list needs LIST-001 handling);
- `backend/tests/unit/**`.

Checked and not needed:
- `api/app.py`: the routes go on the identity router already registered at `/v1`;
- the permission matrix: `firm.manage_users` exists;
- communications: not protected.

### Questions for approval
- **D1. Give staff invitations their own table, tokens and definer functions, reusing the client lockout, rather than making the client ones serve both?** *Recommendation: yes.* The client path, already merged and reviewed, stays untouched.
- **D2. Role changes and revocation go through definer functions that keep at least one active firm administrator, and a revoked person's engagement roles stay as history?** *Recommendation: yes.*
- **D3. Make the local identity provider issue MFA-marked tokens, so fresh-MFA screens work in local development?** *Recommendation: yes.* Local only; real MFA comes from the vendor.
- **D4. Invitations expire after 14 days (client invitations use the SPEC-015 default)?** *Recommendation: yes.*
- **D5. Write the approval file for the paths above?** *Recommendation: yes.*

## Definition of done
- [x] All listed ACs have passing tests that reference them (independent tests deferred by the founder)
- [x] Type check, lint, format, architecture and dependency rules pass
- [x] Every query is tenant-scoped; every endpoint checks authorisation
- [x] Module READMEs and the relevant docs are updated

## Progress log
- `2026-10-09` — Implemented:
  - migration 0033 (staff invitations and tokens; definer functions for tokens, staff membership, firm role and revocation, with last-admin protection);
  - the staff service and routes; the staff accept route; the invitation email (`/join` link);
  - the People tab in Firm admin; the `/join` page;
  - the local provider issues MFA-marked tokens (D3).

  Deviation: the plan let firm admins open the list without a fresh sign-in. That would have needed a role check outside `authorise` (AUTHZ-001), so the list is `firm.manage_users` like every other action and asks for a recent sign-in, as Walls does. `identity/authz` was not touched.

  Tests and checks:
  - backend unit and web 172 passed; the gates pass; migration 0033 applies, rolls back and reapplies;
  - a local smoke passed: a founder signed up and invited a practice leader; the invitation was accepted (email matched regardless of case) and its reuse refused; demoting the last admin was refused; admin was handed over and the founder's access revoked. The smoke data was removed.
- `2026-10-09` — Design written for founder review; SSO held for the vendor decision.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|

## Handoff
