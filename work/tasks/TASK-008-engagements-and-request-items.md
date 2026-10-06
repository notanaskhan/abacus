---
id: TASK-008
title: Engagements and request items through the API
spec: SPEC-000
acceptance_criteria: [AC-4, AC-5, AC-6, AC-7, AC-8]
risk_zone: amber
status: in-review
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
- [x] ADR-102 accepted by the founder (2026-10-06, "accept ADR-102"); its path added to the approval file at the founder's instruction


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

### Interface contract (tests written independently — ADR-078)
**HTTP** (`create_app()`; authenticate with `FakeIdentityProvider` + `configure_verifier`, reset with `reset_verifier()`; seed firms, users, memberships and engagement members as the superuser):
- `POST /v1/engagements` with body `{name, client_name, client_entity_name, fiscal_period_start, fiscal_period_end}`:
  - All three names must be 1–200 characters after trimming. Dates are ISO dates with end > start. Unknown fields are rejected.
  - Success is **201** with `{id, name, type: "audit", status: "active", client_name, client_entity_name, fiscal_period_start, fiscal_period_end, created_at, team: [{user_id, display_name, role}]}`.
  - Allowed for firm_admin and practice_leader. Any other user, or one with no firm role, gets **403** `{"detail": "forbidden"}`.
- **AC-4.** One transaction, and none of it happens if any step fails:
  - one `engagements` row with the caller's tenant;
  - one `clients` row and one `client_entities` row;
  - one `engagement_members` row `(creator, engagement_partner)`;
  - audit events `client.created`, `client_entity.created`, `engagement.created`, `engagement_member.added`, all with the creator as actor;
  - one outbox row `engagement.created` whose payload has `engagement_id`.
  - The creator appears in `team` as `engagement_partner`.
- `GET /v1/engagements` → **200**, a list of summaries (the same fields without `team`), newest first:
  - firm_admin and quality_partner see every engagement in the firm;
  - others see the engagements they're members of in a role that allows `engagement.read_metadata`;
  - nothing from another firm (**AC-5**).
- `GET /v1/engagements/{id}` → **200** with metadata and team.
  - The id doesn't exist, or belongs to another firm → **404** `{"detail": "not found"}`. The two must be indistinguishable (**AC-5**, §12).
  - Same firm, but no allowing role → **403**.
- `POST /v1/engagements/{id}/request-items` with `{description (1–2000), audit_area (1–100)}`:
  - → **201** `{id, engagement_id, description, audit_area, status: "open", created_at}`, with audit event `request_item.created` and outbox event `request_item.created` (payload has `request_item_id` and `engagement_id`) (**AC-7**).
  - Allowed for engagement_partner, manager and senior on that engagement. A reviewer or staff member → **403**, and nothing written (**AC-8**). Other firm or missing → **404**.
  - The first item creates the engagement's single request list; later items reuse it.
- `GET /v1/engagements/{id}/request-items` → **200**, items in creation order, for engagement members whose role allows `request_item.read`.
  - A firm_admin who isn't a member → **403** (**AC-6**: metadata 200, content 403).
  - Other firm → **404**.
- **Validation errors** → **422** `{"detail": [{loc, msg, type}]}`. They never include the submitted input or `ctx`.
- **AC-5** three ways, with Firm A's engagement and Firm B's user:
  - the API: list, get and items;
  - the repository: `abacus.modules.engagements.repository.list_engagements` and `get_engagement` under Firm B's `tenant_session`;
  - a direct `SELECT` on `engagements`/`request_items` under Firm B's `tenant_session`.

  Firm A's rows never appear.

**Database (migration 0005)**
- New tenant tables `clients`, `client_entities`, `engagements`, `request_lists`, `request_items`, all with forced RLS.
- Composite foreign keys keep related rows in one firm and consistent:
  - an entity of another client → FK error;
  - a request item whose list belongs to another engagement → FK error;
  - a `created_by` user who isn't a firm member → FK error.
- `engagement_members (tenant_id, engagement_id)` → `engagements`.
- CHECKs: `fiscal_period_end > fiscal_period_start`; status and type values.
- Grants:
  - `abacus_app` has no DELETE on the five tables;
  - no UPDATE on `clients`, `client_entities` or `request_lists`;
  - it gains INSERT on `engagement_members`.
- `schema_check`:
  - `TABLE_OWNERS` lists every table;
  - it reports `<t>: no owner in TABLE_OWNERS` for an unlisted table and `<t>: in TABLE_OWNERS but missing` for a listed one that doesn't exist.

**Static rule LIST-001** (`src/abacus/modules/*/repository.py` only): a `def`/`async def` named `list_*` that doesn't call `visible(...)` (bare name or attribute) is flagged.

**OpenAPI**
- `abacus.api.export_openapi.document()` returns identical text on repeated calls (sorted keys, 2-space indent, trailing newline).
- Operation IDs are `me`, `create_engagement`, `list_engagements`, `get_engagement`, `create_request_item` and `list_request_items`.
- Every operation carries `x-abacus-action`.
- `packages/api-client/openapi.json` equals `document()` (drift).

**Route introspection** now covers the five new routes, with the actions in §3.

#### Contract revision 1 (2026-10-06, from both stage 4 reviews)
**Database (migration 0006, column grants)**
- `abacus_app` may INSERT only these columns:
  - `clients (id, tenant_id, name)`;
  - `client_entities (id, tenant_id, client_id, name)`;
  - `engagements (id, tenant_id, client_id, client_entity_id, name, fiscal_period_start, fiscal_period_end, created_by)`;
  - `request_lists (id, tenant_id, engagement_id)`;
  - `request_items (id, tenant_id, engagement_id, request_list_id, description, audit_area, created_by)`;
  - `engagement_members (tenant_id, engagement_id, user_id, role)`.
- It may UPDATE only `status` on `engagements` and `request_items`.
- `schema_check`:
  - the declared insert columns now apply to every table in `APP_INSERT_COLUMNS`, not only insert-only tables;
  - the new `APP_UPDATE_COLUMNS` check reports `<t>: abacus_app may UPDATE <t>.<column>` (and `may INSERT`) for extra columns.

**Behaviour**
- `POST .../request-items` resolves and share-locks the engagement inside its unit of work (`engagements.api.lock_ref`) and authorises there. Missing or other-firm engagement → 404; denied → 403, with nothing written.
- The first item for an engagement also records audit event `request_list.created` (target `request_list`, `after.engagement_id`). `request_item.created` audit events carry `after.engagement_id`.
- The creator's `engagement_member.added` audit event carries `after.user_id` = the creator. `identity.api` exports `add_creator_as_partner(tx, ctx, engagement_id)` (no user or role arguments); `add_engagement_member` is gone.
- Names (`name`, `client_name`, `client_entity_name`, `audit_area`) reject any control character (U+0000–U+001F, U+007F) with a 422. `description` allows `\n` and `\t` only. NUL never reaches the database.
- Any unhandled exception → **500** `{"detail": "internal error"}`, logged as `api.unexpected_error` with the exception class name only.
- `create_app()` raises `RuntimeError` when `environment == "production"` and `identity.api.WALL_SAFE` is False (walls gate the first real firm).
- `engagements.api` exports `EngagementCreated`, `EngagementRef`, `get_ref`, `lock_ref`, `router`. `requests.api` exports `RequestItemCreated`, `router`.

**OpenAPI**
- Top-level `security: [{"bearer": []}]` and `components.securitySchemes.bearer` (http, bearer, JWT).
- Every operation documents `401`, `403`, `404` (`ErrorOut {detail}`) and `422` (`ValidationErrorOut {detail: [FieldErrorOut {loc, msg, type}]}`).
- No schema anywhere declares `input` or `ctx`.

**Static rules**
- **LIST-001** (`src/abacus/modules/*/repository.py` and `*/repository/*.py`):
  - Applies to a function named `list_*`/`all_*`/`search_*`, or one that calls `.all()`, unless it's in `LIST_EXEMPT`.
  - Such a function must pass a `visible(...)` call inside a `.where(...)` argument.
  - That `visible` call's second argument must be a string literal naming a read action in the matrix.
- **BOUND-002** (`src/abacus/modules/*`): imports of another module must be allowed by `MODULE_DEPENDENCIES`:
  - `identity` → none;
  - `organisations` → none;
  - `engagements` → identity, organisations;
  - `requests` → identity, engagements;
  - any other module → identity.
- **OWN-001** (`src/abacus/modules/*`): `__tablename__ = "<t>"`, `Table("<t>", …)`, and upper-case SQL statements (`SELECT`/`INSERT`/`UPDATE`/`DELETE`/`WITH` … `FROM|JOIN|INTO|UPDATE <t>`) must name tables whose `TABLE_OWNERS` owner is the file's module.

### Approval file text
```yaml
task: TASK-008
approved_by: founder
expires: 2026-10-27
paths:
  - docs/adr/ADR-102-visible-takes-action-and-engagement-column.md
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
| @hey-api/openapi-ts (dev, packages/api-client) | 0.99.0 | Generated API client (ADR-013) | already allowlisted |

## Progress log
- `2026-10-06` — Created from the SPEC-000 breakdown approved by the founder. Not started.
- `2026-10-06` — Design drafted (§1–7, Q1–Q5) for founder review.
- `2026-10-06` — Approved with all recommendations; approval file written at the founder's instruction.
- `2026-10-06` — Implemented steps 1–5. Smoke-tested end to end: AC-4 to AC-8, Firm B 404s, 422 without input echo. Interface contract written. ADR-103 accepted (Q1).
- `2026-10-06` — Security review (Sonnet): changes requested. Fixed 1–8 (walls production gate; creator-only member add with audited user; NUL and control-character rejection plus a 500 handler; lock-then-authorise; column grants in 0006). Notes 9–17 recorded.
- `2026-10-06` — Architecture review (Sonnet): changes requested. Fixed S1–S4, S7, S8 and S10 (RETURNING, DTOs, OpenAPI errors and security, stricter LIST-001). Also S5 as BOUND-002 and S9 as OWN-001 (in `banned_patterns`, since `pyproject.toml` isn't in the approval). Notes recorded as follow-ups (Gotchas).
- `2026-10-06` — ADR-102 accepted by the founder.
- `2026-10-06` — Independent tests (Sonnet): no implementation bugs. `make check` found unclassified error-model fields (fixed), and TASK-007 tests seeding members without engagements (seeding fixed by the test author; assertions unchanged).
- `2026-10-06` — `make check` exit 0: 4,023 unit + 682 integration, coverage 97 %, schema_check clean, api-client drift check on and clean.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| Plain glossary table names; ownership in `TABLE_OWNERS` + OWN-001 | Glossary is binding vocabulary | ADR-103 (accepted) |
| Creator becomes `engagement_partner` via `add_creator_as_partner` only | AC-4; nobody else can be added until `engagement.member_add` has a route | No |
| Engagement detail = metadata only | One action per route; ADR-024 | No |
| Core `insert(...).returning()` executed immediately, not ORM add/flush | Ordered writes across composite FKs; UOW-001 bans flush | No |
| Writes lock the engagement row and authorise inside the unit of work | Close check-then-act (security S5, architecture S3) | No |
| Module dependency direction in BOUND-002 (banned_patterns), not import-linter | `pyproject.toml` not in this approval; same effect | No |
| Production refuses to start until walls exist (`WALL_SAFE`) | Founder decision: walls gate the first real firm | No |

## Gotchas and discoveries
- From the stage 4 reviews: these follow-ups are recorded, not fixed here.
  - Pagination envelope `{items, next_cursor}` before the frontend relies on bare arrays (ADR-013 breaking change otherwise). Decide in TASK-012.
  - Client dedupe when client management lands (every engagement creates a client today).
  - A `requests.api.get_item_ref` for evidence (TASK-009).
  - Reference docs `backend-module.md` and `unit-of-work.md` (TASK-015).
  - A security alert on `engagement_member.added` by a firm_admin creator (residual ADR-024 risk; needs alerting, TASK-013).
  - Type-check `packages/api-client` in `make check`.
  - CI `pnpm install --frozen-lockfile --ignore-scripts`.
  - Same-firm 403 vs 404 reveals existence within a firm (by design, §3).
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
- **Current state:** Done pending review. PR open on `task-008-engagements`; `make check` exit 0.
- **Exact next step:** Confirm CI. Founder review (amber; diff review optional). Merge, delete `work/approvals/TASK-008.yaml`, mark done; then TASK-009 design (needs `requests.api.get_item_ref`, see Gotchas).
- **Uncommitted or partial work:** none.
- **Known failing checks:** none.
- **Open issues:** branch protection off; follow-ups listed in Gotchas.
