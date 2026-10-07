---
id: TASK-016
title: Ethical walls
spec: SPEC-002
acceptance_criteria: [AC-1, AC-2, AC-3, AC-4, AC-5, AC-6, AC-7, AC-8, AC-9, AC-10, AC-11]
risk_zone: red
status: awaiting-plan-approval
branch: task-016-ethical-walls
worktree:
created: 2026-10-07
updated: 2026-10-07
---

> **Rules for the agent working this task**
> - Read this whole file before doing anything. Continue from the *Handoff* section if it has content.
> - Load only the files listed under *Context to load*, plus what the plan requires.
> - Amber and red tasks: do not write code until the plan is marked approved.
> - If scope must change, **stop** and add it to *Questions for the human*.
> - Never mark `done` until every item in *Definition of done* passes.
> - Append to the *Progress log* before ending any session, even mid-task.

## Objective
Implement SPEC-002: a firm admin walls a person off from a client. Walls override every role in `authorise` and `visible()`, stop agents and system runs acting for that person, and unlock production (`WALL_SAFE`).

## Scope
All of SPEC-002 (AC-1 to AC-11): the API only, the `wall.read` matrix action (Q2), 404 for walled engagements (Q1), and runs stopped at their next step (Q3).

## Context to load
- Spec: `docs/specs/SPEC-002-ethical-walls.md`
- ADRs: ADR-026, ADR-020, ADR-023, ADR-024, ADR-025, ADR-027
- Reference: `docs/architecture/reference/tenancy-and-authz.md`, `backend-module.md`, `unit-of-work.md`

## Plan
- [ ] Plan approved by human (required for amber and red)

### Design (for founder review)
**1. Data (identity; migration `0012`).**
- Table `ethical_walls`:
  - columns: `tenant_id`, `id`, `user_id`, `client_id`, `status` (active|removed), `created_by`, `created_at`, `removed_by`, `removed_at`;
  - forced RLS;
  - a unique partial index for one active wall per (tenant, user, client);
  - the app inserts, and updates only `status`/`removed_by`/`removed_at`, under a forward-only trigger (active → removed) with no deletes;
  - foreign keys to `memberships (tenant_id, user_id)` and `clients (tenant_id, id)`.
- Owned by identity. `schema_check` maps are updated.

**2. Where a wall is checked: `authorise`, layer 2, before roles.**
- `Resource` gains `client_id`. Engagement resources carry it, because `engagements.get_ref`/`lock_ref` load it with the row: `EngagementRef` gains `client_id`.
- A human whose active walls include `resource.client_id` is denied at layer `wall`. So is an agent whose initiator is walled, through the existing live initiator check. A system context is denied when its `on_behalf_of` person is walled, which is a new live check.
- The person's active walled client IDs are read once per request: cached on the context for that request, through a contextvar like `recording_checks`.

**3. `visible()`: engagement IDs to clients, without breaking module boundaries.**
- Walls name clients, but list queries filter on an engagement-ID column, and only the engagements module may read `engagements`.
- Recommend (Q1): the engagements module registers, at import, a function that turns an engagement-ID column into its client-ID scalar subquery (`register_engagement_client(...)` in `identity.api`). It names its own table, so OWN-001 is respected; identity never imports engagements, so there is no cycle. A test fails if the registration is missing.
- `visible()` ANDs the existing filter with `client_of(engagement_id) NOT IN (:walled)` when the person has walls; otherwise the filter is unchanged.

**4. 404 for walled engagements (SPEC Q1).** `Forbidden` at layer `wall` maps to the API's 404 body (the same as a missing engagement). Other `Forbidden` layers stay 403.

**5. Runs (SPEC Q3).** Retrieval stages and screening already authorise their action at each step, and `Forbidden` is terminal there, so a newly walled person's run fails with `forbidden` at its next step. The tests prove it.

**6. API (identity routes).**
- `POST /v1/walls` (`wall.create`, fresh MFA) returns 201 `WallOut`, 404 for an unknown member or client, and 409 `wall_exists`.
- `DELETE /v1/walls/{id}` (`wall.remove`, fresh MFA) returns 204.
- `GET /v1/walls` (`wall.read`, fresh MFA) lists walls, through `visible`-style tenant scoping.
- Audit events: `wall.created` and `wall.removed`. Then `make generate`.

**7. Matrix (SPEC Q2).** Add `wall.read: {firm_admin: allow, mfa_recent: required}` and regenerate `_matrix.py`. The matrix-generated test now also asserts `walled: deny` for every role and engagement-scoped action.

**8. `WALL_SAFE = True`.** Production startup is allowed; the TASK-007 guard test is updated accordingly.

### Questions for approval
- **Q1. Dependency inversion for `visible()`:**
  - (recommended) engagements registers an engagement→client lookup with identity at import;
  - or a database view owned by engagements, granted to the app;
  - or denormalise `client_id` onto every engagement-scoped table (large migration).
- **Q2. Approval file paths:**
  - `backend/src/abacus/modules/identity/**`, `backend/src/abacus/modules/engagements/**`;
  - `backend/src/abacus/api/**`, `backend/migrations/**`;
  - `docs/architecture/permission-matrix.yaml`;
  - `backend/src/abacus_tools/quality/schema_check.py`, `backend/src/abacus_tools/quality/banned_patterns.py` and its test;
  - `packages/api-client/**` (regenerated);
  - `.claude/skills/**` (the tenancy skill and reference note on walls);
  - `docs/architecture/reference/tenancy-and-authz.md` is not protected.

### Steps
1. Approval file; migration 0012; the matrix change.
2. The wall check in `authorise` and `visible()`, the registration, and 404 mapping.
3. The routes, generation, and `WALL_SAFE`.
4. The interface contract, independent tests (red), two reviews, `make check` (CI-like, with the compose DB stopped), PR, line-by-line review.

## Definition of done
- [ ] All listed ACs have passing tests that reference them
- [ ] Type check passes
- [ ] Lint and format pass
- [ ] Architecture and dependency rules pass
- [ ] Full test suite passes; no tests skipped, weakened or deleted
- [ ] Security scan passes; no secrets committed
- [ ] No new dependencies, or each one approved and listed below
- [ ] Every query is tenant-scoped; every endpoint checks authorisation
- [ ] AI calls (if any) go through the gateway with limits, logging and passing evals
- [ ] Module README and relevant docs updated
- [ ] Decisions below reviewed; ADR raised where needed

## New dependencies
| Package | Version | Why | Approved by |
|---|---|---|---|

## Progress log
- `2026-10-07` — Created from SPEC-002 (approved by the founder). Design drafted (§1–8, Q1–Q2) for founder review.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|

## Gotchas and discoveries
-

## Questions for the human
-

## Handoff
- **Current state:** Design drafted; awaiting founder approval (red). No code.
- **Exact next step:** On approval, write `work/approvals/TASK-016.yaml` with the Q2 paths, then step 1.
