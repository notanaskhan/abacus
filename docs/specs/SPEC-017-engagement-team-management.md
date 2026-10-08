---
id: SPEC-017
title: Engagement team management
status: approved
owner: founder
risk_zone: red
related_adrs: [ADR-024, ADR-026, ADR-020, ADR-007]
related_specs: [SPEC-002, SPEC-013, SPEC-015, SPEC-016]
created: 2026-10-08
updated: 2026-10-08
---

> **Instructions for coding agents**
> - Implement only what this spec describes. Anything not listed here is out of scope.
> - If anything is ambiguous or contradicts an ADR, **stop** and add it to *Open questions*. Do not guess.
> - Every test must reference the acceptance criterion (AC-n) it proves.
> - This spec must be `approved` with no open questions before implementation starts.

## 1. Summary
An engagement's partner and managers can staff it:
- add firm members with an engagement role (partner, manager, senior, staff, reviewer);
- change a member's role;
- remove a member.

Today only the creator (as partner) and self-joining admins are ever members, so nobody else can work an engagement. The matrix already holds `engagement.member_add` and `engagement.member_remove` for partners and managers. This spec adds the service, the routes, the rules (Q1 to Q4), a notification for the person added, and a **People** tab in the SPA that combines the team with the client contacts.

## 2. Problem and context
Phase 2 increment 1 (engagement setup) needs real teams:
- review assignment picks from the team;
- engagement roles drive every permission check;
- staff can't see an engagement they aren't on.

## 3. Actors
| Actor | Role in this feature |
|---|---|
| Engagement partners | Add, change and remove any team member (Q1) |
| Managers | Add, change and remove seniors, staff and reviewers (Q1) |
| Firm members | Are added, and get a notification |

## 4. Goals and non-goals
**Goals**
- **Candidates:** `GET /v1/engagements/{id}/team/candidates` returns the firm's active **staff** members (never client users) who aren't on the team and aren't walled from the engagement's client. It is authorised by `engagement.member_add`.
- **Add:** `POST /v1/engagements/{id}/team {user_id, role}`, audited as `engagement_member.added`. It emits `engagement_member.added`, and the person added is notified (a new notification kind).
- **Change role:** `PUT /v1/engagements/{id}/team/{user_id} {role}`, authorised by `engagement.member_add` and audited as `engagement_member.role_changed`.
- **Remove:** `DELETE /v1/engagements/{id}/team/{user_id}`, authorised by `engagement.member_remove` and audited as `engagement_member.removed`. Their next request on the engagement is refused.
- **The rules (Q1 to Q4):**
  - managers can't add, change or remove partners and managers;
  - an engagement always keeps at least one partner;
  - walled people can't be added;
  - archived engagements can't be changed (the existing archived-write rule);
  - client users are never staff members (SPEC-015).
- **UI:** the engagement's **People** tab (it replaces Contacts):
  - **Team:** names and roles, with Add person, Change role and Remove, each confirmed;
  - **Client contacts:** the existing section.

  Firm admins who self-joined appear as reviewers.

**Non-goals**
- Firm-level membership management: inviting staff to the firm, changing firm roles, deactivating people. That comes with the identity vendor (TASK-014).
- Bulk staffing, and copying a team from last year.
- Practice or office scoping.

## 5. User stories and acceptance criteria
- **AC-1** Given a partner, when they open Add person, then they see the firm's active staff members who aren't on the team and aren't walled from this client, and can add one with any role. `engagement_member.added` is audited and the person is notified.
- **AC-2** Given a manager, then they can add, change and remove seniors, staff and reviewers only. Trying to give, change or remove partner or manager roles is refused (403).
- **AC-3** Given an engagement with one partner, when anyone removes that partner or changes their role, then it is refused (409 `last_partner`).
- **AC-4** Given a person walled from the engagement's client, then they aren't offered, and adding them by ID is refused with the same 404 as an unknown person (no wall disclosure, SPEC-002 Q1).
- **AC-5** Given a member removed, then their next request on the engagement is refused, and their in-flight review assignments on it are released (audited).
- **AC-6** Given a client user's ID, or a user from another firm, then adding them is refused (404).
- **AC-7** Given the People tab, then partners and managers see the actions they may take, others see the team read-only, and every change asks for confirmation.

## 6. Behaviour and flows
1. **Add:** lock the engagement, authorise, then check the role limits, the candidate (active staff, not walled, not a member), and insert. Audit, emit, notify.
2. **Change or remove:** lock the engagement and authorise, then check the role limits and the last-partner rule, then update or delete. For a removal, release the person's review assignments on this engagement. Audit.

## 7. Domain and data changes
- **`engagement_members`:** UPDATE on `role`, and DELETE for staff roles. Both happen through the service and only under the engagement lock. The existing kind trigger still applies.
- **Notifications:** the kind `engagement_member.added` (the person added).

## 8. Interfaces
| Interface | Purpose |
|---|---|
| `GET /v1/engagements/{id}/team` | The team (existing data, now a route): `engagement.read_metadata` |
| `GET /v1/engagements/{id}/team/candidates` | Who can be added: `engagement.member_add` |
| `POST /v1/engagements/{id}/team` | Add: `engagement.member_add` |
| `PUT /v1/engagements/{id}/team/{user_id}` | Change role: `engagement.member_add` |
| `DELETE /v1/engagements/{id}/team/{user_id}` | Remove: `engagement.member_remove` |

## 9. Authorisation and tenancy
- **Matrix:** unchanged (the actions exist). The role limits in Q1 are enforced by the service, because the matrix can't express "which role you may grant".
- **Walls:** checked for the person being added.
- **Tenancy:** RLS, as everywhere.

## 10. AI behaviour
None.

## 11. Integrations
None.

## 12. Edge cases and failure modes
- **Concurrent changes:** they serialise on the engagement lock, so the last-partner check can't race.
- **Removing yourself:** allowed within the same rules (a partner can leave if another partner remains).
- **A member who left the firm:** removing them still works. They are no longer offered as a candidate.

## 13. Security and privacy
- **No disclosure:** walls never leak (AC-4).
- **Least privilege:** managers can't escalate (AC-2).
- **Audit:** every change is audited with who did it, the person and the role.

## 14. Audit trail and evidence integrity
`engagement_member.added`, `engagement_member.role_changed`, `engagement_member.removed`, and `review.released` for released assignments.

## 15. Observability
Unchanged.

## 16. Performance and scale
Small: teams of under 50 people.

## 17. UX
- **The People tab:** a Team table (name, role, actions) and an "Add person" dialog with a searchable candidate list and a role select that offers only the roles the caller may grant.
- **Client contacts:** below the team, as today.

## 18. Test plan
| AC | Test type | Description |
|---|---|---|
| AC-1, AC-6 | integration | Candidates exclude members, walled people and client users; add audits and notifies |
| AC-2 | integration | Manager limits |
| AC-3 | integration | Last partner |
| AC-4 | integration | A wall gives the same 404 as an unknown person |
| AC-5 | integration | Removal refuses the next request and releases assignments |
| AC-7 | component | The People tab shows actions by role, with confirmations |

## 19. Rollout
A migration for the grants. No flag.

## 20. Open questions
None. Answered by the founder on 2026-10-08 (all recommendations):
- [x] **Q1: who may grant which roles.** *Recommendation:* partners grant, change and remove any role. Managers handle seniors, staff and reviewers only.
- [x] **Q2: the last partner.** *Recommendation:* every engagement keeps at least one partner. Removing or demoting the last one is refused, so another partner must be added first.
- [x] **Q3: one tab or two.** *Recommendation:* one **People** tab, with the team first and client contacts below. It replaces the Contacts tab, so there's one place for "who's on this".
- [x] **Q4: notifications.** *Recommendation:* notify the person added (`engagement_member.added`). Role changes and removals aren't notified in v1, though they are audited.

## 21. Future / explicitly deferred
- Firm membership management (with the identity vendor).
- Copying last year's team.
- Bulk staffing.
- Capacity and scheduling.
