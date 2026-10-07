---
id: TASK-016
title: Ethical walls
spec: SPEC-002
acceptance_criteria: [AC-1, AC-2, AC-3, AC-4, AC-5, AC-6, AC-7, AC-8, AC-9, AC-10, AC-11]
risk_zone: red
status: in-progress
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
- [x] Plan approved by human (founder, 2026-10-07: all recommendations, Q1–Q2)

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

### Interface contract — TASK-016 (tests written independently — ADR-078)
**Imports:**
- `abacus.modules.identity.api`: `register_engagement_client`, `authorise`, `visible`, `Resource`, `Forbidden`, `WALL_SAFE`.
- `abacus.modules.identity.service`: `create_wall`, `remove_wall_by_id`, `list_walls`, `WallView`, `WallExists`.
- `abacus.modules.identity.repository`: `walled_clients`, `ethical_walls`.
- `abacus.modules.engagements.api`: `get_ref`, `lock_ref`, `EngagementRef` (now has `client_id`).

**Routes:**
- `POST /v1/walls {user_id, client_id}` (`wall.create`, firm admin, MFA within 15 min):
  - 201 `WallOut {id, user_id, client_id, status:"active", created_by, created_at, removed_by:null, removed_at:null}`;
  - 409 `{"detail":"wall_exists"}` when an active wall already exists for that pair;
  - 404 for a user who isn't a member of the firm, or a client not in the firm;
  - 403 without recent MFA or for non-admins;
  - audit `wall.created`.
- `POST /v1/walls/{wall_id}/remove` (`wall.remove`, same rules): 200 `WallOut` with status `removed`, `removed_by`/`removed_at` set; 404 for an unknown or already removed wall; audit `wall.removed`.
- `GET /v1/walls` (`wall.list`, same rules): every wall of the firm, newest first.
- After a removal, a new wall for the same pair can be created.

**Enforcement (SPEC-002 AC-4–AC-8, AC-11):**
- `authorise` with an engagement `Resource` raises `Forbidden(layer="wall")`, before relationship and role checks, when the acting person is walled from the engagement's client. The acting person is:
  - the user, for `AuthContext`;
  - `on_behalf_of`, for `SystemContext`;
  - `initiator.user_id`, for `AgentContext`.

  It applies to every role, including firm_admin, practice_leader and quality_partner, for every engagement-scoped action. Firm-level resources (`Resource.firm`) are never walled.
- `Resource.client_id` is used when set (`EngagementRef.resource()` sets it). When it is absent, the client comes from the registered lookup. When nothing is registered, a person with any active wall is denied (fail closed).
- `visible(ctx, read_action, col)` excludes rows whose engagement's client the acting person is walled from. It correlates correctly when the outer query is on `engagements` itself, or on another table's `engagement_id`.
- **API:** `Forbidden` at layer `wall` answers 404 with exactly the not-found body; other layers stay 403. Walled engagements are missing from `GET /v1/engagements` and from every list route (request items, evidence versions, screening results).
- **New engagements:** an engagement later created for a walled client is walled too (AC-6).
- **Runs (AC-7):** a retrieval or screening run acting for a person walled after it started ends failed with code `forbidden` at its next step.
- **Other clients (AC-8)** are unaffected.
- **Removal (AC-9):** after a removal, access follows roles again on the next request.
- **`WALL_SAFE`** is True, and `create_app` starts with `environment="production"`, given its other settings.

**Database (migration 0012):**
- `ethical_walls` has forced RLS.
- At most one active wall per (tenant, user, client), through a partial unique index.
- The app may insert `id, tenant_id, user_id, client_id, created_by`, and update only `status, removed_by, removed_at`, under a forward-only trigger: a removed wall can't change, and identity columns are immutable.
- No delete.
- CHECK: removed ⇔ `removed_at` and `removed_by` set.
- Foreign keys to memberships (user, created_by, removed_by) and clients.
- The downgrade refuses when walls exist.

**Existing tests whose pinned facts change** (update them; don't weaken them):
- `tests/unit/identity/test_permission_matrix.py`: it fakes `authz.engagement_role`; it must also fake `authz.walled_clients` (returning no walls), and gain walled cases.
- `tests/unit/api/test_app_gates.py::test_ac20_creating_routes_answer_201`: the POST set gains `/v1/walls` (201) and `/v1/walls/{wall_id}/remove` (200).
- Any test asserting production refuses to start because walls aren't safe.

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
- `2026-10-07` — Approved with all recommendations: Q1 engagements registers the engagement→client lookup; Q2 the approval file was written at the founder's instruction.
- `2026-10-07` — Implemented and committed (f147743): migration 0012; the identity repository and service; routes (POST /v1/walls, POST /v1/walls/{id}/remove, GET /v1/walls); the wall check in `authorise` (layer `wall`) and in `visible()` (NOT EXISTS subquery); the engagements registration (`register_engagement_client`); the 404 mapping; `wall.read` in the matrix; `WALL_SAFE=True`; the client regenerated; `schema_check` and LIST-001 updated. Static checks pass.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| The matrix action is `wall.list`, not SPEC-002's `wall.read` | `*.read` verbs mean engagement-scoped reads that `visible()` filters; listing walls is firm-level and needs fresh MFA | No |
| Removal is `POST /v1/walls/{id}/remove` returning the removed wall, not `DELETE` (204) | AbacusRouter requires a response model on every route | No (spec §8 note) |

## Gotchas and discoveries
-

## Questions for the human
-

## Handoff
- **Current state:** Implementation committed on `task-016-ethical-walls` (f147743, pushed). Approval file `work/approvals/TASK-016.yaml` exists locally (gitignored).
- **Fixed:** the client subquery now aliases `Engagement` and correlates explicitly (`correlate_except`), as does the walls EXISTS; 288 engagements and identity integration tests pass. Previously: `backend/src/abacus/modules/engagements/repository.py` `client_column()` builds `select(Engagement.client_id).where(Engagement.id == engagement_id).scalar_subquery()`. When `engagement_id` is `Engagement.id` itself (the engagements list), it doesn't correlate to the outer row → "more than one row returned by a subquery" (it also fails in `test_identity` `visible` probes). Fix: `e = aliased(Engagement)`; `select(e.client_id).where(e.id == engagement_id).scalar_subquery()`. Then rerun `uv run pytest tests/integration/test_engagements.py tests/integration/test_identity.py`.
- **Expected test-pin updates (for the test author, not the implementer):**
  - `tests/unit/identity/test_permission_matrix.py`: fakes `authz.engagement_role` but not the new `authz.walled_clients`, so it now hits the DB; fake it.
  - `tests/unit/api/test_app_gates.py::test_ac20_creating_routes_answer_201`: the POST route set gains `/v1/walls` (201) and `/v1/walls/{wall_id}/remove` (200).
  - The TASK-007 `WALL_SAFE` production-guard test, if one pins the refusal.
- **Exact next step:**
  1. Fix the bug above.
  2. Write the interface contract (SPEC-002 AC-1–11; routes; 404 on layer `wall`; agents, system runs and `visible`; DB forward-only and unique-active; the registration and its fail-closed behaviour).
  3. Launch the Sonnet test author on its own branch `task-016-ethical-walls-tests` (push there only; I cherry-pick). Include the pin updates.
  4. Run the security and architecture reviews.
  5. Run the full suite with the compose DB stopped (`docker stop abacus-db-1`; restart after).
  6. PR, then the founder's line-by-line review (red). Merge without waiting for CI if the founder says so; delete the approval file; mark done.
- **Elsewhere:** TASK-014 is blocked on founder inputs (AWS account/credentials, budget, Terraform state, WorkOS approval, OTel/Sentry targets). Other ADR gaps (ADR-038 reconciliation, ADR-040 egress, ADR-031 for SQLAlchemy models) need specs. Main is up to date through PR #19.
