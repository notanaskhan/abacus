---
id: TASK-008
title: Engagements and request items through the API
spec: SPEC-000
acceptance_criteria: [AC-4, AC-5, AC-6, AC-7, AC-8]
risk_zone: amber
status: in-progress
branch: task-008-engagements
worktree:
created: 2026-10-06
updated: 2026-10-06
---

> **Rules for the agent working this task**
> - Read this whole file before doing anything. Continue from the *Handoff* section if it has content.
> - Load only the files listed under *Context to load*, plus what the plan requires.
> - Amber and red tasks: do not write code until the plan is marked approved.
> - If scope must change, **stop** and add it to *Questions for the human*.
> - Never mark `done` until every item in *Definition of done* passes.
> - Append to the *Progress log* before ending any session, even mid-task.

## Objective
Engagement and request-item modules with routes, services and repositories; OpenAPI export and the generated TypeScript client (switches on the api-client drift check).

## Scope
In:
- clients and client entities (organisations), engagements (engagements), request lists and request items (requests);
- the five SPEC-000 §8 routes except retrievals (TASK-010);
- the creator becomes an engagement member;
- the OpenAPI export and the generated TypeScript client, which switch on the drift check;
- the list-method `visible()` rule (ADR-027).

Out: retrievals, evidence and screening on the item list (TASK-009–011); engagement update, archive and member management routes; client management routes; the UI (TASK-012).

## Context to load
- Spec: `docs/specs/SPEC-000-walking-skeleton.md`
- ADRs: ADR-008, ADR-012, ADR-013

## Plan
- [x] Plan approved by human (founder, 2026-10-06: "approved, proceed")
- [x] Approval file `work/approvals/TASK-008.yaml` written by the agent at the founder's instruction (2026-10-06); approved by founder: paths under *Approval file text*, expires 2026-10-27
- [x] Q1–Q5: all recommendations approved (2026-10-06)


### Design (for founder review)

**1. Tables** (migration `0005`). All are tenant tables with `id uuid PK` plus `UNIQUE (tenant_id, id)`. Every foreign key includes `tenant_id`, so a row can never point into another firm.

| Module | Table | Columns |
|---|---|---|
| organisations | `clients` | `name` (1–200), `created_at` |
| organisations | `client_entities` | `client_id → clients`, `name`, `created_at` |
| engagements | `engagements` | `client_id`, `client_entity_id → client_entities (same client)`, `name`, `type` (`audit`), `fiscal_period_start`, `fiscal_period_end` (CHECK end > start), `status` (`active`, `archived`), `created_by`, `created_at` |
| requests | `request_lists` | `engagement_id → engagements`, UNIQUE per engagement |
| requests | `request_items` | `request_list_id`, `engagement_id`, `description` (1–2000), `audit_area` (1–100), `status` (`open`, `received`, `ready_for_review`, `needs_revision`; default `open`), `created_by`, `created_at` |

- The FK `engagement_members (tenant_id, engagement_id) → engagements` is added here.
- Grants:
  - the app gets SELECT and INSERT everywhere, no DELETE;
  - UPDATE stays only on `engagements` and `request_items`, for status changes in later tasks;
  - `engagement_members` gains INSERT, for the creator.
- Engagement metadata is Confidential; descriptions are Confidential (ADR-031).

**2. Module layout (ADR-008, ADR-012).** Each module has `models.py` (ORM), `repository.py`, `service.py`, `routes.py`, `api.py` and `README.md`. The ORM `Base` lives in `kernel.db` (one `DeclarativeBase` with a naming convention). Cross-module calls go only through `api.py`. Dependencies are one-way: requests → engagements → organisations, and engagements → identity.

**3. Routes** (each declares one action):
| Method | Path | Action | Behaviour |
|---|---|---|---|
| POST | `/v1/engagements` | `engagement.create` | One `uow`:<ul><li>create the client and client entity (`organisations.api`);</li><li>create the engagement;</li><li>add the creator as a member (`identity.api.add_engagement_member`);</li><li>audit events `client.created`, `client_entity.created`, `engagement.created` and `engagement_member.added`;</li><li>outbox event `engagement.created`.</li></ul>Returns 201 with the metadata (AC-4). |
| GET | `/v1/engagements` | `engagement.read_metadata` | List filtered by `visible()` (AC-5, AC-6). |
| GET | `/v1/engagements/{id}` | `engagement.read_metadata` | **Metadata only**: name, status, team, fiscal period, client and entity names. |
| POST | `/v1/engagements/{id}/request-items` | `request_item.create` | Creates the request list on first use. Status `open`. Audit event `request_item.created`; outbox event `request_item.created` (AC-7, AC-8). |
| GET | `/v1/engagements/{id}/request-items` | `request_item.read` | Content: items only for now. Evidence and screening join in TASK-009–011. |

- **Lookups:** `engagements.api.get_ref(ctx, id) -> EngagementRef(tenant_id, id, archived) | None`, read under RLS.
  - Not found → **404**. This covers a Firm B guess at Firm A's ID, with no existence leak (§12).
  - Found but denied → **403**. Within one firm, existence isn't secret.
- `authorise(ctx, action, Resource.engagement(ref.tenant_id, ref.id, archived=ref.archived))` runs **before** any write.
- **Team:** `identity.api.engagement_team(ctx, engagement_id)` reads members under RLS and display names through the identity engine, for exactly those user IDs.

**4. List rule (ADR-027 enforcement).** New banned pattern **LIST-001**: every `def list_*` in a module's `repository.py` must call `visible(`.

**5. Validation errors.** A 422 must never echo the submitted input. A handler strips `input` and `ctx` from validation errors, because client content is hostile (AGENTS.md #8).

**6. OpenAPI and client (ADR-013).**
- `abacus/api/export_openapi.py` prints `create_app().openapi()` as sorted JSON. Operation IDs come from route names, so client function names are stable.
- `packages/api-client` gets:
  - `package.json` with `@hey-api/openapi-ts` (allowlisted) pinned;
  - `openapi-ts.config.ts`;
  - the generated `src/`, committed.
- The drift check switches on when `export_openapi.py` exists.

**7. Tests** (independent author, from the interface contract):
- AC-4 to AC-8 over HTTP against real Postgres.
- AC-5 three ways: API, repository, and a direct `tenant_session` query as Firm B.
- Route introspection over the real routes.
- LIST-001 rules.
- An export determinism test.

### Questions for approval
- **Q1. Table names.** ADR-008 says "each module owns tables prefixed with its name", but SPEC-000 §7, the glossary and migration 0004 use unprefixed names (`engagements`, `memberships`). I recommend keeping the glossary names and enforcing ownership with an explicit `TABLE_OWNERS` map in `schema_check` (every table must be listed against its module). That would be recorded as **ADR-103**, superseding ADR-008's prefix line. The alternative is renaming everything now (`identity_users`, `engagements_engagements`, …).
- **Q2. Creator's engagement role.** AC-4 says "the creator becomes an engagement member". I recommend the role `engagement_partner`, audited as `engagement_member.added`. Note the ADR-024 tension: a firm admin who creates an engagement gains content access without the self-join notification. Alternative: the request names the partner, and a creator who is a firm admin joins only through self-join.
- **Q3. `GET /v1/engagements/{id}`.** SPEC §8 says "metadata or full view", but a route declares one action. I recommend metadata only, with content through the content routes (`request-items`), as ADR-024 asks.
- **Q4. Clients.** The matrix has no client action, so clients and entities are created inside `engagement.create`. Client management comes later. Recommend yes.
- **Q5. Request list.** Created on the first item (requests depend on engagements, not the reverse). Recommend yes.

### Approval file text
```yaml
task: TASK-008
approved_by: founder
expires: 2026-10-27
paths:
  - backend/src/abacus/kernel/db/**
  - backend/src/abacus/modules/identity/**
  - backend/src/abacus/api/**
  - backend/src/abacus_tools/quality/schema_check.py
  - backend/src/abacus_tools/quality/banned_patterns.py
  - backend/tests/unit/quality/test_banned_patterns.py
  - packages/api-client/package.json
  - pnpm-lock.yaml
reason: TASK-008 — engagements, request items, OpenAPI export and generated client
```

### Steps
1. Approval file. ADR-103 (if Q1 is approved). `kernel.db.Base`.
2. Migration `0005`; `schema_check` (`TABLE_OWNERS`; insert and update grant checks).
3. Organisations, engagements and requests modules (models → repository → service → routes → api); identity `add_engagement_member` and `engagement_team`; wire `ROUTERS`.
4. Validation-error handler; LIST-001.
5. `export_openapi.py`; the `packages/api-client` generator; generate and commit.
6. Interface contract → independent test author; two Sonnet reviews; `make check`; PR.

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
- `2026-10-06` — Created from the SPEC-000 breakdown approved by the founder. Not started.
- `2026-10-06` — Design drafted (§1–7, Q1–Q5) for founder review.
- `2026-10-06` — Approved with all recommendations; approval file written at the founder's instruction.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|

## Gotchas and discoveries
- From TASK-007: build engagement resources with `Resource.engagement(tenant_id, id, archived=<loaded from the engagements row>)`. Never hard-code `archived=False`; consider having `authorise` load it itself once `engagements` exists.
- Add the FK `engagement_members.engagement_id → engagements` and the app grants this task needs (`INSERT` on `engagement_members` for "creator becomes a member", AC-4).
- `authorise` is not wall-safe (ADR-026). Founder decision 2026-10-06: walls gate the first real firm, not this task.
- HTTP tests for AC-6 and AC-8 land here, with the routes.
- ADR-027/ADR-102 enforcement: add the test that inspects every repository list method and fails if `visible()` is not applied.
- Consider an `EngagementRef` from `engagements.api` that `authorise` accepts and loads itself, closing the check-then-act gap. Make missing and denied engagements answer alike (no 404-vs-403 oracle).
- FastAPI parses request bodies before dependencies run, so an unauthenticated caller can get a 422 that echoes input. Decide on an auth-first approach for body routes.
- Add the `export_openapi` module and the `packages/api-client` generator. That switches the drift check on (Makefile keyed on `backend/src/abacus/api/export_openapi.py`; founder, 2026-10-06).

## Questions for the human
-

## Handoff
- **Current state:** Design drafted; awaiting founder approval (amber). No code.
- **Exact next step:** On approval, write `work/approvals/TASK-008.yaml` with these paths:
  - `backend/src/abacus/kernel/db/**`
  - `backend/src/abacus/modules/identity/**`
  - `backend/src/abacus/api/**`
  - `backend/src/abacus_tools/quality/schema_check.py`
  - `backend/src/abacus_tools/quality/banned_patterns.py`
  - `backend/tests/unit/quality/test_banned_patterns.py`
  - `packages/api-client/package.json`
  - `pnpm-lock.yaml`

  Then follow the Steps.
