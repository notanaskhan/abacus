---
id: TASK-032
title: Engagement team management
spec: SPEC-017
acceptance_criteria: [AC-1, AC-2, AC-3, AC-4, AC-5, AC-6, AC-7]
risk_zone: red
status: awaiting-plan-approval
branch: task-032-team-management
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
Implement SPEC-017 (approved, Q1–Q4): team candidates, adding, changing roles and removing (with the manager limits, the last-partner rule and walls), releasing review assignments on removal, a notification for the person added, and the People tab.

## Scope
All of SPEC-017.

## Context to load
- Spec: `docs/specs/SPEC-017-engagement-team-management.md`
- ADRs: ADR-024, ADR-026, ADR-106
- Code: `identity` (team, walls, repository), `engagements` (service, routes), `evidence` (review assignments), `notifications` (catalogue), `apps/web` (`EngagementLayout`, `Contacts`)

## Plan
- [ ] Plan approved by human

### Design (for founder review)
1. **Changing and removing go through definer functions (D1):**
   - `team_member_set_role(engagement, user, role)` and `team_member_remove(engagement, user)` are SECURITY DEFINER, act in the session's tenant, and handle staff roles only. Both refuse to leave the engagement without a partner (`last_partner`).
   - The app role gets no general UPDATE or DELETE on `engagement_members`, the same pattern as `remove_client_member`.
   - Adding uses the existing column INSERT grant.
2. **Rules** (identity `team.py`, inside the caller's unit of work after `lock_ref` and `authorise`):
   - the caller's own engagement role decides the manager limits (Q1): a manager can't grant, change or remove `engagement_partner` or `manager`, and gets 403;
   - candidates come from one identity query: active staff memberships of the firm, not on the team, not walled from the engagement's client (the client comes from the `EngagementRef` that engagements passes in);
   - adding someone who isn't a candidate gets 404 (walls, client users, other firms, AC-4 and AC-6).
3. **Releasing assignments on removal (D2, ADR-106):**
   - identity defines a slot, `register_member_removed(handler)`; evidence registers `release_member_assignments(tx, engagement_id, user_id)`, which clears that person's review assignments on the engagement and audits `review.released` for each;
   - it is called in the same unit of work as the removal;
   - an unregistered slot fails closed (the removal is refused).
4. **Routes** (engagements module, since identity can't import engagements): `GET …/team`, `GET …/team/candidates`, `POST …/team`, `PUT …/team/{user_id}` and `DELETE …/team/{user_id}`.
5. **Notification:** identity emits `EngagementMemberAdded`, and the notifications catalogue gains `engagement_member.added` (the person added).
6. **UI:**
   - the Contacts tab becomes **People**: a Team table with Add person (searchable candidates, roles limited by the caller's role), Change role and Remove, each confirmed, then the existing Client contacts section;
   - the role that decides which actions to show is the caller's own entry in the team list.
7. **Migration 0027:** the two definer functions and their review in `schema_check`.

**Protected paths (approval file):**
- `backend/src/abacus/modules/{identity,engagements,evidence,notifications}/**`;
- `backend/migrations/**`;
- `backend/src/abacus_tools/quality/schema_check.py`, `backend/tests/unit/**`;
- `apps/web` (not protected).

### Questions for approval
- **D1. Role changes and removals go through SECURITY DEFINER functions (staff roles only, last-partner rule enforced in the database), rather than giving the app role UPDATE or DELETE on `engagement_members`?** *Recommendation: yes.* It matches how client members are removed, and the rule holds even against a bug in the service.
- **D2. Review assignments are released through an ADR-106 slot that evidence registers, in the same unit of work as the removal?** *Recommendation: yes.* Identity and engagements can't import evidence.
- **D3. Write the approval file for the protected paths above?** *Recommendation: yes.*

## Definition of done
- [ ] All listed ACs have passing tests that reference them (independent tests deferred by the founder)
- [ ] Type check, lint, format, architecture and dependency rules pass
- [ ] Every query is tenant-scoped; every endpoint checks authorisation
- [ ] Module READMEs and the relevant docs are updated

## Progress log
- `2026-10-08` — SPEC-017 approved and merged (#59). Design written for founder review.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|

## Handoff
