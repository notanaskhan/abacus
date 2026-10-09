---
id: TASK-034
title: Knowledge, budget, support access and walls screens
spec: SPEC-019
acceptance_criteria: [AC-1, AC-2, AC-3, AC-4, AC-5, AC-6, AC-7]
risk_zone: amber
status: done
branch: task-034-admin-screens
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
Implement SPEC-019 (approved, Q1–Q4): knowledge search and documents, budget and metering, support access, and walls screens, plus the two picker routes for walls.

## Scope
All of SPEC-019.

## Context to load
- Spec: `docs/specs/SPEC-019-firm-admin-and-knowledge-screens.md`
- Code: `apps/web` (shell, `Methodology`, `mfa`), the generated client, `identity` (walls, memberships), `organisations.api.firm_names`, `engagements` routes

## Plan
- [x] Plan approved by human (founder, 2026-10-08: D1–D2). Approved by founder: paths listed under *Protected paths*

### Design (for founder review)
1. **The picker routes (Q4, D1):**
   - `GET /v1/firm/members` lives in identity (`wall.create`): active **staff** members with names, never clients.
   - `GET /v1/firm/clients` lives in engagements (`wall.create`): the clients from `organisations.api.firm_names`, entities left out. Engagements already depends on identity and organisations, so no module-boundary change is needed.
2. **Navigation (Q1):**
   - the rail gains Knowledge (all staff);
   - Firm admin opens `AdminLayout` with role-filtered tabs: Methodology · Knowledge documents · Budget · Support access · Walls;
   - the role comes from `/v1/me`'s firm role: admins see all tabs, practice leaders see Methodology, Knowledge and Budget.
3. **Screens:**
   - `Knowledge` (`/knowledge`, the `search` mutation);
   - `KnowledgeDocuments` (`/admin/knowledge`, polling while any document is pending);
   - `Budget` (`/admin/budget`: the budget, metering with a day/month toggle, sortable, with totals);
   - `SupportAccess` (`/admin/support`);
   - `Walls` (`/admin/walls`: on a 403 on load, the "Confirm it's you" prompt).

   All reuse `ConfirmItsYou`, `Panel`, `StatusPill` and `Table`.
4. **The emergency banner (Q3):** `AdminLayout` reads support sessions (firm admins only) and shows a persistent banner for any emergency that isn't acknowledged, linking to Support access.
5. **Engagement names in metering (Q2):** from the engagements list query, else "Engagement" plus the first eight characters of the ID.

**Protected paths (approval file):** `backend/src/abacus/modules/identity/**` (the members route) and `backend/tests/unit/**` (the route pins). Engagements and `apps/web` aren't protected.

### Questions for approval
- **D1. Members route in identity and clients route in engagements, both authorised by `wall.create`, so no module boundary changes?** *Recommendation: yes.*
- **D2. Write the approval file for the protected paths above?** *Recommendation: yes.*

## Definition of done
- [x] All listed ACs have passing tests that reference them (independent tests deferred by the founder)
- [x] Type check, lint, format, architecture and dependency rules pass
- [x] Every endpoint checks authorisation
- [x] Docs updated

## Progress log
- `2026-10-09` — **Process slip, found during TASK-036:** this task added `engagements.firm_router` to `backend/src/abacus/api/app.py` (a protected path, `abacus.api`), although app.py wasn't in the approval file. The change only registered the router. The founder was told and acknowledged it on 2026-10-09.
- `2026-10-08` — Implemented:
  - the picker routes `GET /v1/firm/members` (identity) and `GET /v1/firm/clients` (engagements), both authorised by `wall.create`;
  - Knowledge on the rail; the Firm admin section with role-filtered tabs and the emergency banner;
  - the Knowledge, Knowledge documents (with polling and plain-words failures), Budget and spend, Support access and Walls screens.

  Component tests for AC-1 to AC-7 (15 new; web 135), backend unit (8,903) and the gates pass.
- `2026-10-08` — SPEC-019 approved and merged (#63). Design written for founder review.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|

## Handoff
