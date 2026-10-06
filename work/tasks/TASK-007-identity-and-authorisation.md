---
id: TASK-007
title: Sign-in, memberships, tenant context, authorise and visible
spec: SPEC-000
acceptance_criteria: [AC-1, AC-2, AC-3, AC-6, AC-8]
risk_zone: red
status: done
branch: task-007-identity
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
Users and memberships; sign-in against a local fake OpenID Connect provider behind a token-verification interface (WorkOS later); tenant context resolved from membership on every request; `/v1/me`; `authorise` and `visible`; wiring `docs/architecture/permission-matrix.yaml` into `authorise` and generating permission tests from it (every route declares one action). Decide in the plan: fake OpenID provider in-process (a signed-token stub behind the verification interface) or as a container (then it needs a `containers:` allowlist entry and a SPEC-000 note).

## Scope
In: FastAPI app skeleton (`abacus.api`), users/firms/memberships/engagement_members, token verification, request context, `/v1/me`, `authorise`, `visible`, matrix loader and generated tests, route introspection, static rules (AUTH-001, AUTHZ-001).
Out: engagements and request items routes (TASK-008), ethical walls (ADR-026 — not in SPEC-000's ADR list), client users and grants, agent task scope (TASK-011), browser sessions/cookies (TASK-012), WorkOS (before staging).

## Context to load
- Spec: `docs/specs/SPEC-000-walking-skeleton.md`
- ADRs: ADR-002, ADR-020, ADR-023, ADR-024, ADR-027, ADR-029

## Plan
- [x] Plan approved by human (founder, 2026-10-06: "approved, proceed") — **red: founder reviews the diff line by line before merge**
- [x] Approval file `work/approvals/TASK-007.yaml` written by the agent at the founder's instruction (2026-10-06)
- Approved by founder: paths under *Approval file text*, expires 2026-10-27
- [x] Q1–Q5 answered: all recommendations approved (2026-10-06)
- Red task: the agent drafts the design here; the founder edits or approves it before any code, then reviews the diff line by line (founder decision 2026-10-06).

### Design (for founder review)

**1. Authentication: in-process fake OpenID provider, real verification path.** A `TokenVerifier` protocol in `modules/identity` returns `VerifiedIdentity(issuer, subject, auth_time, mfa: bool)` and nothing else — no roles, no tenant (ADR-029). The one implementation, `JwtVerifier`, checks an RS256 signature against a JWKS, plus `iss`, `aud`, `exp`, `nbf`, `iat` (30 s leeway), with an algorithm allowlist of `RS256` only and every claim required. WorkOS issues the same kind of token, so swapping providers changes configuration (issuer, audience, JWKS source), not code.
The fake provider lives in `abacus_tools/fakes/identity.py`: it generates a key pair, publishes the JWKS and mints tokens for tests and local runs. Product code holds only the public key (`identity_jwks` setting, required outside local/test along with `identity_issuer`/`identity_audience`). Signing keys never exist in product code, and no `/dev/token` route exists in the app. In-process beats a container: nothing to pin or allowlist, and it keeps the verifier honest because it does real signature checks.
Requests use `Authorization: Bearer <token>` only. Browser sessions come with TASK-012.

**2. Tables** (migration `0004`):
| Table | Columns | Tenancy and grants |
|---|---|---|
| `firms` | `tenant_id uuid PK`, `name text`, `created_at` | tenant table (a firm *is* its tenant) |
| `users` | `id uuid PK`, `idp_issuer text`, `idp_subject text` (unique together), `email text`, `display_name text`, `created_at` | **global** (ADR-002); `abacus_app` has no privileges on it |
| `memberships` | `tenant_id`, `id uuid`, `user_id uuid → users`, `firm_role text NULL CHECK IN (firm_admin, practice_leader, quality_partner)`, `status text CHECK IN (active, revoked)`, `created_at`, `revoked_at`; PK `(tenant_id, id)`; unique `(tenant_id, user_id)` | tenant table |
| `engagement_members` | `tenant_id`, `engagement_id uuid`, `user_id uuid`, `role text CHECK IN (engagement_partner, manager, senior, staff, reviewer)`, `created_at`; PK `(tenant_id, engagement_id, user_id)` | tenant table; the FK to `engagements` is added in TASK-008 |
`schema_check` gets `GLOBAL_TABLES = {"users"}`. A global table must have no RLS, no `abacus_app` or `abacus_relay` privileges, and only `SELECT` for `abacus_identity`. Users and memberships are seeded by an `abacus_tools` seed command as owner; provisioning (SCIM, `firm.manage_users`) is later work.

**3. Pre-tenant lookup: role `abacus_identity`.** Sign-in must find a user's memberships before any tenant is known, but forced RLS hides them. This mirrors the relay: `abacus_identity` (bootstrap; LOGIN, BYPASSRLS, NOINHERIT) has `SELECT` on `users`, on `memberships (tenant_id, id, user_id, firm_role, status)` and on `firms (tenant_id, name)` only, enforced by `schema_check`. It is reached only through `identity_engine()`, and **UOW-002** is extended so only `modules/identity/repository.py` may import it.

**4. Request context** (FastAPI dependency `current_context`, in identity; routes get it via `abacus.api`):
1. Verify the bearer token; otherwise **401**.
2. Resolve the user by `(iss, sub)`; an unknown user gets **403**.
3. Load the user's *active* memberships fresh on every request, with no cache, so revocation bites on the next request (AC-3).
4. Choose the active tenant. With one membership, use it. With several, the client names one in `X-Abacus-Tenant`, which is accepted only if it matches an active membership (ADR-002: never a client value alone). If it's missing or unknown, return **403**. With no memberships, return **403** (AC-2).
5. Build `RequestContext(user_id, membership_id, firm_role, tenant: TenantContext(tenant_id, "human", str(user_id)), mfa_at)`.
Firm roles come from the database, never from token claims (ADR-029).

**5. `authorise(ctx, action, resource)` and `visible(ctx, resource_type)`** — the only permission logic (ADR-020).
- The matrix YAML is loaded and validated at import: unknown roles, conditions or actions are an error.
- `authorise` evaluates the four layers in order (ADR-023):
  1. Tenancy: `resource.tenant_id == ctx.tenant`.
  2. Relationships: active membership; engagement membership if the resource is engagement-scoped.
  3. Roles: firm role and engagement role (loaded via `tenant_session`) mapped through the matrix.
  4. Attributes: `archived_write`, `mfa_recent` (15 min, from the token's `auth_time` + `amr`), `requires: reason`.
- Deny by default; any layer denying means deny; it raises `Forbidden(layer, action)`, which becomes **403**, and each decision is logged with the denying layer.
- Conditions with no model yet evaluate to **deny**, never allow, until their task adds them: `in_scope`, `firm_setting(...)`, `assigned_only`, `client_visible_only`, `task_scope`, `walled`, `access_expired`.
- `visible` returns a SQLAlchemy filter: firm_admin and `read_metadata` → every engagement in the tenant; otherwise engagements where the user is a member.

**6. Every route declares one action (ADR-012/027).**
- `abacus.api` provides `AbacusRouter` whose verbs require `action=` (a matrix action, or `SELF` for `/v1/me` only) and `response_model=`.
- The dependency records the declared action. If a handler returns successfully without `authorise`/`visible` having been called for it, the response becomes **500** and is logged: fail closed.
- Route introspection test: every route has the auth dependency, a response model, exactly one action, and that action is in the matrix; `SELF` is allowed only on `/v1/me`.

**7. Generated matrix tests** (`tests/unit/identity/test_permission_matrix.py`): every role × every action is checked against the matrix, so every allow and every deny is covered, plus each layer denying independently. AC-6 and AC-8 are proved here at `authorise` level (firm_admin: `read_metadata` allow, `engagement.read` deny without membership; reviewer: `request_item.create` deny). The HTTP-level tests for them land with the routes in TASK-008.

**8. Static rules.** **AUTH-001**: no token-claim access outside `modules/identity/tokens.py` (ADR-029). **AUTHZ-001**: no `firm_role`/`.role` comparisons outside `modules/identity/authz/` (ADR-020). **TENANT-002**: `X-Abacus-Tenant` is read only by the context builder.

**9. Dependencies.** `fastapi`, `httpx` (test client) and `cryptography` are already approved. **New: `pyjwt[crypto]`**, which needs an allowlist entry (Q1).

### Questions for approval
- **Q1 — JWT library.** Recommend adding `pyjwt` (with `cryptography`) to the allowlist: mature, the standard for verifying JWKS-signed tokens, and what a WorkOS verifier would use. The alternative, hand-rolled JWS on `cryptography`, means writing red-zone crypto code ourselves: not recommended.
- **Q2 — `engagement_members` here, FK in TASK-008.** Relationships are authorisation data (ADR-027), so the identity module owns the table. Recommend yes.
- **Q3 — AC-6/AC-8 split.** Prove them at `authorise` level here; HTTP 403 tests in TASK-008 when the routes exist. Recommend yes.
- **Q4 — Unmodelled conditions deny.** `in_scope`, `firm_setting`, client and agent conditions, and walls all deny until their tasks. Practice leaders and quality partners therefore can't read content yet. Recommend yes; walls (ADR-026) get their own spec.
- **Q5 — Several memberships.** `X-Abacus-Tenant`, validated against memberships, is required only when the user has more than one. Recommend yes.

### Interface contract (tests written independently — ADR-078)
**Imports**
- `from abacus.modules.identity.api import AbacusRouter, AbacusRoute, SELF, ACTION_KEY, TENANT_HEADER, AuthContext, Resource, Forbidden, UnknownAction, MFA_RECENT, authorise, visible, current_context, current_signed_in, declared_action, router, JwtVerifier, TokenVerifier, VerifiedIdentity, InvalidToken, configure_verifier`
- `from abacus.api import create_app`
- `from abacus_tools.fakes.identity import FakeIdentityProvider, ISSUER, AUDIENCE`
- `from abacus_tools.codegen.permission_matrix import render, SOURCE, TARGET, main`
- `from abacus.kernel.db import configure_identity_engine, identity_engine`

**Database** (migration 0004; fixtures: `migrated_db` gains `identity_url`, and `configure_identity_engine` is called)
- `firms(tenant_id PK, name)`, `users(id, idp_issuer, idp_subject, email, display_name; unique (idp_issuer, idp_subject))` (global, no `tenant_id`), `memberships(tenant_id, id, user_id, firm_role NULL in (firm_admin, practice_leader, quality_partner), status in (active, revoked), revoked_at; unique (tenant_id, user_id); revoked ⇔ revoked_at set)`, `engagement_members(tenant_id, engagement_id, user_id, role in (engagement_partner, manager, senior, staff, reviewer); FK (tenant_id, user_id) → memberships)`.
- Tenant tables have forced RLS. `abacus_app` may only SELECT `firms`, `memberships` and `engagement_members`, and has **no** privileges on `users`.
- `abacus_identity`: BYPASSRLS, read-only by default (`default_transaction_read_only`). It may SELECT all of `users`, `memberships (tenant_id, id, user_id, firm_role, status)` and `firms (tenant_id, name)`, and nothing else. Seed rows as the superuser (`migrated_db.superuser_dsn`).
- `schema_check` reports:
  - `abacus_identity: has <PRIV> on <table>` and `abacus_identity: may <PRIV> <table>.<column>` for anything beyond those grants (the relay's checks use the same format);
  - `users: abacus_app has <PRIV> on a non-tenant table` / `users: abacus_app may <PRIV> users.<column>`;
  - `abacus_identity: has <ATTRIBUTE>`, `is a member of <role>`, and the sequence checks, as for the relay.

**Tokens** (`JwtVerifier(issuer=, audience=, jwks=<JSON str>)`, `.verify(token) -> VerifiedIdentity(issuer, subject, mfa_at)`)
- Valid: RS256, `kid` in the JWKS, `iss`, `aud`, `exp`, `iat` and `sub` all present and right; 30 s leeway.
- Everything else raises `InvalidToken`, including: wrong key, unknown or missing `kid`, `alg` none/HS256, expired, `iat`/`nbf` in the future beyond leeway, wrong `iss` or `aud`, a missing required claim, empty or over-255-character `sub`, over 8192 bytes, garbage, and an empty JWKS (`{"keys": []}`).
- `mfa_at` is the `auth_time` (UTC) only if `amr` contains `"mfa"`; otherwise `None`. Role-like claims (`role`, `roles`, `org_role`) are ignored.
- `FakeIdentityProvider(issuer=ISSUER, audience=AUDIENCE, kid="fake-1")`: `.jwks() -> str`, `.verifier() -> JwtVerifier`, `.token(subject, *, mfa=False, auth_time=None, expires_in=300, **claims) -> str` (claims override). Use `configure_verifier(idp.verifier())`.

**Request context** (HTTP via `httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app()))`)
- No or invalid bearer token → **401** with `WWW-Authenticate: Bearer`. Valid token for an unknown user → **403**.
- `GET /v1/me` (action `SELF`) → `{user_id, email, display_name, memberships: [{tenant_id, firm_name, firm_role}], active_tenant_id}`.
  - `memberships` lists active memberships only, ordered by firm name.
  - `active_tenant_id` is set only when there is exactly one membership.
  - Works with zero or several memberships, and never needs `X-Abacus-Tenant`.
- Action routes (`current_context`):
  - Exactly one active membership → that tenant (**AC-1**: `ctx.tenant.tenant_id` is the membership's tenant, `actor_kind="human"`, `actor_id=str(user_id)`).
  - Several → `X-Abacus-Tenant` must name one of them; missing, malformed or not a membership → **403**.
  - Zero → **403** (**AC-2**).
  - Revoked membership: the next request with the same still-valid token → **403** (**AC-3**). Nothing is cached.
  - Firm role comes from `memberships`, never from the token.

**Routing**
- `AbacusRouter(prefix=, tags=)` has `.get/.post/.put/.patch/.delete(path, *, action, response_model, status_code=None)`. An action not in the matrix (other than `SELF`) or `response_model=None` → `ValueError` at registration.
- `declared_action(route)` returns the action (stored in `openapi_extra[ACTION_KEY]`).
- A route that returns status < 400 without calling `authorise`/`visible` for its declared action → **500** `{"detail": "internal error"}`, logged as `authz.unchecked_route`. A `Forbidden` from `authorise` → **403** `{"detail": "forbidden"}`, never naming the layer.
- Route introspection over `create_app().routes`:
  - every route is an `AbacusRoute` with a declared action that is in the matrix, or `SELF`;
  - `SELF` is allowed only on `/v1/me`;
  - every route has a `response_model`;
  - no docs or openapi routes.
- Tests may mount their own `AbacusRouter` on a `FastAPI()` app (with the same `Forbidden` handler; or append to `abacus.api.app.ROUTERS` before `create_app()`) to exercise action routes.

**authorise(ctx, action, resource, *, reason=None)** (async; returns `None` or raises `Forbidden(action, layer)` with `.layer` in `tenancy | relationship | role | attribute`). Layers in order:
1. `resource.tenant_id != ctx.tenant_id` → `tenancy`.
2. Roles held = `ctx.firm_role` (if any) ∪ the user's `engagement_members.role` for `resource.engagement_id` (if given; read under RLS). None → `relationship`.
3. If any held role's matrix value is `deny`, or none is `allow` → `role`. `in_scope`, `firm_setting(...)`, `assigned_only`, `client_visible_only` and `task_scope` are **not** allow.
4. `resource.archived` and the action's verb is not `read`/`read_metadata`/`read_log` → `attribute`. `mfa_recent: required` and `ctx.mfa_at` is None or older than `MFA_RECENT` (15 min) → `attribute`. `requires: reason` and `reason` is empty or whitespace → `attribute`.
- An action not in the matrix → `UnknownAction` (a `ValueError`).
- AC-6 at this level: a firm_admin with no engagement membership is allowed `engagement.read_metadata` and denied `engagement.read`, `request_item.read` and `evidence.read`.
- AC-8 at this level: a reviewer is denied `request_item.create`.
- Decisions are logged (`authz.allowed` / `authz.denied` with `action`, `layer`, `tenant_id`, `user_id`).

**visible(ctx, action, engagement_id_column) -> ColumnElement[bool]**
- Read actions only; anything else → `ValueError`. Unknown action → `UnknownAction`.
- Firm role `allow` → true (all rows in the tenant).
- Otherwise → the rows whose engagement the user is a member of, in a role whose value is `allow`; none → false.
- Prove it against a probe tenant table with an `engagement_id` column, under `tenant_session`.

**Generated matrix**
- `render(SOURCE.read_text()) == TARGET.read_text()` (drift test); `main(["--check"])` returns 0.
- Generated tests over every `(role, action)` in the YAML check the matrix-driven decisions. For human firm and engagement roles, `allow` → no raise and anything else → `Forbidden`, with ctx and roles arranged so layers 1, 2 and 4 pass. Agent, system and client roles have no context type yet and are out of scope here.
- Each layer denies independently.
- An unknown role, decision or modifier in the matrix source makes the module fail to import: test via `matrix._rule`/`_decision`, which raise `ValueError`.

**Static rules**
- **UOW-003**: `identity_engine`/`configure_identity_engine` outside `kernel/db`, `identity/repository.py` and `tests/integration/conftest.py`.
- **AUTH-001**: importing `jwt` outside `identity/tokens.py` and `abacus_tools/fakes/identity.py`.
- **AUTHZ-001**: in `src/abacus/` outside `identity/authz/`, a comparison whose operand is a `.role`/`.firm_role`/`.roles` attribute, a name `role`/`firm_role`/`roles`, or a matrix role-name string; also a `match` case on a role-name string.
- **TENANT-002**: a string containing `x-abacus-tenant` (any case) outside `identity/service.py`, `banned_patterns.py` and `tests/`.

**Config**
- New settings `identity_database_url` (SecretStr, restricted), `identity_issuer`, `identity_audience` and `identity_jwks`. All four are required outside local/test.
- Local defaults: issuer `https://identity.abacus.local`, audience `abacus-api`, JWKS `{"keys": []}` (verifies nothing).

#### Contract revision 1 (2026-10-06, from the security review)
**authorise / visible**
- The request guard records an action only when `authorise` **returns** (allowed), or when `visible` builds a filter. So a route that catches `Forbidden` and carries on still gets 500, and so does one whose `authorise` raised and was swallowed.
- `notify: engagement_team` is an obligation the platform can't meet yet. Any action that carries it denies at layer `attribute` (today that is `engagement.self_join`: firm_admin is denied).
- `Resource` has no defaults any more. Build it with `Resource.firm(tenant_id)` or `Resource.engagement(tenant_id, engagement_id, *, archived: bool)`, which requires `archived`. The positional `Resource(tenant_id, engagement_id, archived)` still works.
- `visible`:
  - raises `ValueError` for a read action carrying `mfa_recent`, `requires` or `notify`;
  - its subquery also filters `engagement_members.tenant_id == ctx.tenant_id`.
- The module docstring states it is **not wall-safe** (ADR-026 not modelled).

**Tokens**
- Refused with `InvalidToken`:
  - `exp - iat > 3600` (`MAX_LIFETIME_SECONDS`);
  - a token over 8192 **bytes** (UTF-8), not characters.
- JWKS keys are ignored (so tokens signed by them fail) unless they are RSA, at least 2048 bits (`MIN_RSA_BITS`), and declare `alg` RS256 or no `alg`.
- `mfa_at` is `None` when `auth_time` is in the future beyond leeway, is ≤ 0, or would overflow.
- `configure_verifier` raises `RuntimeError` unless `settings().environment` is `local` or `test`.

**Routing**
- `AbacusRouter.websocket`, `.add_api_websocket_route` and `.add_route` raise `TypeError`.
- `TENANT_HEADER` is no longer exported from `identity.api`: use the literal `"X-Abacus-Tenant"` in tests.

**Database**
- The identity engine connects with `default_transaction_read_only=on` and `statement_timeout=5000`.
- `schema_check` reports:
  - `abacus_identity: default_transaction_read_only is not on` when the role setting is missing;
  - `<bypass role>: can execute <lo function>` for large-object functions, on both bypass roles.

**Static rules** (all `include=("src/abacus/*",)` unless noted)
- **UOW-003** now also catches:
  - bare names and parameters `identity_engine`/`configure_identity_engine`/`identity_database_url`;
  - `from abacus.kernel.db import *`.
  Exclusions: `kernel/db/*`, `kernel/config.py`, `identity/repository.py`, `tests/integration/conftest.py`, `tests/unit/kernel/test_config.py`. It applies to all scanned files.
- **AUTH-001** applies to all scanned files. It catches the modules `jwt`, `jose`, `josepy`, `jwcrypto`, `authlib`, `python_jose`, including via `importlib.import_module("…")`/`__import__("…")`.
- **AUTH-002** (new): the string `"authorization"` (any case, trimmed) or the identifier `authorization`, outside `identity/routing.py` and `identity/service.py`.
- **AUTHZ-002** (new): any `.firm_role` attribute outside `src/abacus/modules/identity/`.
- **TENANT-002**: now only in `src/abacus/`; also catches the identifiers `x_abacus_tenant` and `TENANT_HEADER`. Exclusions: `identity/service.py`, `identity/routing.py`.
- **ROUTE-001** (new): the identifiers `APIRouter`, `APIRoute`, `FastAPI`, `Starlette`, `Mount`, `WebSocketRoute`, `APIWebSocketRoute`, `add_api_route`, `add_route`, `add_websocket_route`, `websocket`, `mount`, `include_router` and `dependency_overrides`, outside `identity/routing.py` and `api/app.py`.
- **ROUTE-002** (new): the identifier `SELF` outside `identity/routing.py`, `identity/routes.py` and `identity/api.py`.
- **CTX-001** (new): a call to `AuthContext(...)` or `TenantContext(...)` outside `identity/service.py` and `kernel/db/*`.

#### Contract revision 2 (2026-10-06, from the architecture and test review)
- `identity.api` also exports `reset_verifier()` (clears the override and the settings cache) and `token_verifier()`. `JwtVerifier.key_count` gives the number of usable keys.
- Outside local and test, building the verifier from settings with no usable key raises `RuntimeError`. `create_app()` builds the verifier eagerly, so the error appears at startup.
- `schema_check` reports `<role>: bypasses row-level security, not reviewed` for any non-superuser BYPASSRLS role not in `BYPASS_ROLE_GRANTS`.
- `render()` raises `ValueError("permission matrix: duplicate key ...")` for a duplicate key at any level.
- Static rules:
  - **AUTHZ-001** flags a comparison only when a role-shaped operand (`.role`/`.firm_role`/`.roles`, or the names `role`/`firm_role`/`roles`) meets a firm or engagement role name (or a tuple, list or set containing one), or a `match` on a role-shaped subject. Role names are now: firm_admin, practice_leader, quality_partner, engagement_partner, manager, senior, staff, reviewer. `agent`, `system` and client roles are dropped. `role is None` and `message.role == "assistant"` are not flagged.
  - **AUTH-002**: the string `"authorization"`, a parameter named `authorization`, or an import of `fastapi.security*`. Attributes named `authorization` are no longer flagged.
  - **ROUTE-001**:
    - importing `APIRouter`, `APIRoute`, `APIWebSocketRoute`, `FastAPI`, `Starlette`, `Mount`, `Route`, `Router`, `WebSocketRoute`, `BaseHTTPMiddleware` or `StaticFiles` from `fastapi*`/`starlette*`, or `fastapi.<one of those>`;
    - any `.dependency_overrides`;
    - a *call* `.add_api_route`/`.add_route`/`.add_websocket_route`/`.add_api_websocket_route`/`.websocket`/`.mount`/`.include_router`/`.add_middleware`.
  - **CTX-001**: a call to `AuthContext(...)` outside `identity/service.py`, and `replace`/`copy`/`deepcopy`/`__replace__` called with an argument whose name contains `ctx` or `context`. `TenantContext(...)` is no longer flagged: agent and system contexts need it.
  - **AUTHZ-003** (new, `src/abacus/*` except `identity/authz/*`): a literal `archived=` keyword in a call to `engagement(...)`/`Resource(...)`, or a literal third positional argument to `Resource(...)`.
- ADR-102 (proposed) records the `visible(ctx, action, engagement_id_column)` signature.

### Approval file text
```yaml
task: TASK-007
approved_by: founder
expires: 2026-10-27
paths:
  - Makefile
  - .claude/hooks/_protected.py
  - .github/CODEOWNERS
  - docs/architecture/protected-paths.md
  - docs/architecture/dependency-allowlist.yaml
  - backend/pyproject.toml
  - backend/uv.lock
  - backend/migrations/bootstrap.sql
  - backend/migrations/bootstrap-local.sql
  - backend/src/abacus/kernel/db/**
  - backend/src/abacus/modules/identity/**
  - backend/src/abacus/api/**
  - backend/src/abacus_tools/quality/schema_check.py
  - backend/src/abacus_tools/quality/banned_patterns.py
  - backend/tests/unit/quality/test_banned_patterns.py
reason: TASK-007 — identity, request context, authorise and visible
```

### Steps
1. Protect first: add `modules/identity/**` and `api/**` to the hook, CODEOWNERS and `protected-paths.md` (with approval).
2. Allowlist `pyjwt`; `uv add fastapi httpx pyjwt[crypto]`.
3. `bootstrap.sql`: `abacus_identity` role; settings for `identity_database_url`, `identity_issuer`, `identity_audience`, `identity_jwks`.
4. Migration `0004`; `schema_check` (`GLOBAL_TABLES`, identity-role checks).
5. Identity module: `tokens.py`, `repository.py`, `context.py`, `authz/` (matrix, `authorise`, `visible`), `api.py` exports.
6. `abacus.api`: app factory, `AbacusRouter`, error handlers, `/v1/me`.
7. `abacus_tools`: fake provider and seed command. Static rules. Module README; `tenancy-and-authz.md` reference.
8. Independent test author (Sonnet) writes tests from the contract; two Sonnet reviews; `make check`; PR for founder line-by-line review.

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
| fastapi | 0.142.2 | HTTP API (ADR-012) | already allowlisted |
| httpx | 0.28.1 | ASGI test client | already allowlisted |
| pyjwt[crypto] | 2.15.1 | Bearer-token verification against JWKS | founder, 2026-10-06 (Q1) |

## Progress log
- `2026-10-06` — Created from the SPEC-000 breakdown approved by the founder. Not started.
- `2026-10-06` — Design drafted (§1–9, Q1–Q5) for founder review.
- `2026-10-06` — Approved with all recommendations; approval file written at the founder's instruction. Authorisation goes in `modules/identity/authz/` (the path already protected), not `authorisation.py`.
- `2026-10-06` — Implemented steps 1–7 (protect, allowlist + deps, bootstrap role, migration 0004 + schema_check, identity module, `abacus.api`, fake provider, matrix codegen, static rules). Smoke-tested end to end (401/403/500/revocation). Seed command dropped: tests seed as superuser; a local seed comes with TASK-012 sign-in. Static rule for the identity engine is a separate UOW-003 rather than extending UOW-002 (clearer message). Interface contract written for the independent test author.
- `2026-10-06` — Security review (Sonnet): changes requested; S1/S2 blockers and S4–S18 fixed (contract revision 1). S3 (walls) and S19 (`audit_event.read`) decided by the founder.
- `2026-10-06` — Independent tests (Sonnet) round 1: found the JWKS crash on non-RS256 keys (fixed); DB-001 exclusion for `test_identity.py`.
- `2026-10-06` — Architecture and test review (Sonnet): changes requested.
  - B1: the api-client drift check is keyed on `export_openapi.py` (founder decision; `Makefile` added to the approval).
  - A1: ADR-102 proposed.
  - A2–A7, A9 fixed (contract revision 2).
  - A8, A10 and A11 are notes; A10 is in the TASK-008 gotchas, and A11 is now a test.
  - Test findings T1–T9 were addressed by the test author in round 2. T10: test commits are now separate from implementation commits.
- `2026-10-06` — `make check` exit 0: 3,863 unit + 414 integration, coverage 97 %, schema_check clean, api-client drift skipped until TASK-008.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| `visible(ctx, action, engagement_id_column)` | Decisions are per action (ADR-024 metadata vs content); columns differ by table | ADR-102 (proposed) |
| Routing (`AbacusRouter`) lives in identity, not `abacus.api` | Modules can't import `abacus.api` (ADR-101 layers) | No |
| Matrix compiled to `authz/_matrix.py`, drift-tested | Runtime image has no YAML parser and ships product code only | No |
| Unmodelled matrix conditions and `notify` obligations deny | Deny by default (ADR-023) until their tasks build them | No |
| Not wall-safe; walls gate the first real firm | ADR-026 not in SPEC-000 (founder, 2026-10-06) | No |
| api-client drift check keyed on `export_openapi.py` | The exporter and client are TASK-008 scope (founder, 2026-10-06) | No |
| Seed command deferred to TASK-012 | Tests seed as the superuser; local sign-in comes with the frontend | No |

## Gotchas and discoveries
-

## Questions for the human
- [x] Answered 2026-10-06 (founder): api-client drift check re-keyed on `backend/src/abacus/api/export_openapi.py` existing (TASK-008 adds the exporter and client); `Makefile` added to the approval file at the founder's instruction.
- [x] Answered 2026-10-06 (founder: "approved, proceed with your recommendations") — walls gate the first real firm, not TASK-008; firm_admin keeps `audit_event.read`, audit events stay content-free.
- **Walls before engagement data (security review S3).** `authorise` is not wall-safe: ADR-026 isn't modelled, and SPEC-000 doesn't list it. Recommend: no engagement route ships to a real firm before walls exist. SPEC-000 is synthetic-data-only, so TASK-008 may proceed; the wall spec is a gate before the first real firm, not before TASK-008.
- **`audit_event.read` for firm_admin (S19).** The matrix lets firm_admin read audit events without an engagement relationship. That is safe while audit events carry only identifiers and references, which TASK-006 enforces: `Target`/`Ref` are identifier-only. Recommend: keep it, and keep audit events content-free.

## Handoff
- **Current state:** Done. PR #7 merged (rebase) 2026-10-06 after founder review and green CI; approval file deleted. ADR-102 is still `proposed`, awaiting the founder's accept or reject.
- **Exact next step:** none (TASK-008).
