---
id: TASK-007
title: Sign-in, memberships, tenant context, authorise and visible
spec: SPEC-000
acceptance_criteria: [AC-1, AC-2, AC-3, AC-6, AC-8]
risk_zone: red
status: in-progress
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
- [ ] Plan approved by human (required for amber and red)
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

**8. Static rules.** **AUTH-001**: no token-claim access outside `modules/identity/tokens.py` (ADR-029). **AUTHZ-001**: no `firm_role`/`.role` comparisons outside `modules/identity/authorisation.py` (ADR-020). **TENANT-002**: `X-Abacus-Tenant` is read only by the context builder.

**9. Dependencies.** `fastapi`, `httpx` (test client) and `cryptography` are already approved. **New: `pyjwt[crypto]`**, which needs an allowlist entry (Q1).

### Questions for approval
- **Q1 — JWT library.** Recommend adding `pyjwt` (with `cryptography`) to the allowlist: mature, the standard for verifying JWKS-signed tokens, and what a WorkOS verifier would use. The alternative, hand-rolled JWS on `cryptography`, means writing red-zone crypto code ourselves: not recommended.
- **Q2 — `engagement_members` here, FK in TASK-008.** Relationships are authorisation data (ADR-027), so the identity module owns the table. Recommend yes.
- **Q3 — AC-6/AC-8 split.** Prove them at `authorise` level here; HTTP 403 tests in TASK-008 when the routes exist. Recommend yes.
- **Q4 — Unmodelled conditions deny.** `in_scope`, `firm_setting`, client and agent conditions, and walls all deny until their tasks. Practice leaders and quality partners therefore can't read content yet. Recommend yes; walls (ADR-026) get their own spec.
- **Q5 — Several memberships.** `X-Abacus-Tenant`, validated against memberships, is required only when the user has more than one. Recommend yes.

### Steps
1. Protect first: add `modules/identity/**` and `api/**` to the hook, CODEOWNERS and `protected-paths.md` (with approval).
2. Allowlist `pyjwt`; `uv add fastapi httpx pyjwt[crypto]`.
3. `bootstrap.sql`: `abacus_identity` role; settings for `identity_database_url`, `identity_issuer`, `identity_audience`, `identity_jwks`.
4. Migration `0004`; `schema_check` (`GLOBAL_TABLES`, identity-role checks).
5. Identity module: `tokens.py`, `repository.py`, `context.py`, `authorisation.py` (matrix, `authorise`, `visible`), `api.py` exports.
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

## Progress log
- `2026-10-06` — Created from the SPEC-000 breakdown approved by the founder. Not started.
- `2026-10-06` — Design drafted (§1–9, Q1–Q5) for founder review.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|

## Gotchas and discoveries
-

## Questions for the human
-

## Handoff
- **Current state:** Design drafted; awaiting founder approval (red). No code.
- **Exact next step:** On approval, write `work/approvals/TASK-007.yaml` (paths: `migrations/bootstrap*.sql`, `migrations/versions/0004_*`, `kernel/config.py`, `kernel/db/**`, `modules/identity/**`, `api/**`, `docs/architecture/dependency-allowlist.yaml`, `docs/architecture/protected-paths.md`, `.claude/hooks/_protected.py`, `.github/CODEOWNERS`, `schema_check.py`, `banned_patterns.py`, `tests/unit/quality/test_banned_patterns.py`), then follow Steps.
