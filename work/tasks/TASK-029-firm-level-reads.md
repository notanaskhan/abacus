---
id: TASK-029
title: Firm-level reads for engagement roles
spec: SPEC-014
acceptance_criteria: [AC-1, AC-2, AC-3, AC-4, AC-5, AC-6, AC-7]
risk_zone: red
status: awaiting-plan-approval
branch: task-029-firm-reads
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
Implement SPEC-014 (approved, Q1–Q3): on firm-level read actions, a person's engagement roles on non-archived engagements count toward the matrix decision.

## Scope
All of SPEC-014. Excluded: firm-level writes and practice scope.

## Context to load
- Spec: `docs/specs/SPEC-014-firm-level-reads-for-engagement-roles.md`
- ADRs: ADR-020, ADR-106
- Code: `identity/authz/__init__.py` (`_roles`, `authorise`, the walls cache, `register_engagement_client`), `identity/repository.py`, `engagements/api.py`, the generated matrix tests

## Plan
- [ ] Plan approved by human

### Design (for founder review)
1. **A slot (D1, ADR-106):**
   - `register_active_engagements(subquery: () -> Select[UUID])` in identity authz;
   - `engagements.api` registers `select(Engagement.id).where(Engagement.status != "archived")` beside its existing client registration;
   - without the registration, engagement roles never count at firm level (fail closed).
2. **The lookup:** `engagement_roles_in_firm(tenant, user, active)` in identity's repository returns the distinct roles from `engagement_members` where the engagement is in `active()`. It runs under the tenant.
3. **`_roles`:** for a person (`AuthContext`, not a support context) on a firm-level resource and a **read** action, add those roles **only when the firm role doesn't already decide `allow`** (D2, which saves a query for admins). Results are cached per request in a ContextVar, like the walls cache.
4. **The decision is unchanged:** only `allow` grants and `deny` wins. Conditional decisions (`in_scope` and the rest) are already non-grants, which satisfies AC-5 with no new code.
5. **Tests:**
   - the generated matrix tests gain firm-level-read cases for every engagement role: allowed exactly where the matrix says `allow`, and refused when the only engagement is archived;
   - a write probe and a conditional probe (AC-4, AC-5);
   - agent, system and support unchanged (AC-6, AC-7).

**Protected paths (approval file):** `backend/src/abacus/modules/{identity,engagements}/**`, `backend/tests/unit/**`.

### Questions for approval
- **D1. Register the active-engagement subquery through a new identity slot (ADR-106), with engagements registering it, so identity never imports engagements?** *Recommendation: yes.*
- **D2. Skip the engagement-role lookup when the firm role already allows the action?** *Recommendation: yes.* Same result, one query fewer.
- **D3. Write the approval file for the protected paths above?** *Recommendation: yes.*

## Definition of done
- [ ] All listed ACs have passing tests that reference them
- [ ] Type check, lint, format, architecture and dependency rules pass
- [ ] Every query is tenant-scoped; every endpoint checks authorisation
- [ ] Module READMEs and the relevant docs are updated

## Progress log
- `2026-10-08` — SPEC-014 approved and merged (#52). Design written for founder review.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|

## Questions for the human
- Design questions D1–D3 (above).

## Handoff
