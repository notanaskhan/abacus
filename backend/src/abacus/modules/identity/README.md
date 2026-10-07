# identity

Who someone is, which firm they act in, and what they may do. PROTECTED (red zone).

## Public interface (`api.py`)

| Name | Use |
|---|---|
| `AbacusRouter` | Every module's router. Each route declares `action=` (a matrix action, or `SELF` for `/v1/me`) and `response_model=`; authentication is attached automatically. |
| `current_context` | FastAPI dependency giving the `AuthContext` (tenant from a validated membership). |
| `authorise(ctx, action, resource, *, reason=None)` | The only permission check. Raises `Forbidden` (403). |
| `visible(ctx, action, engagement_id_column)` | Filter for list queries over engagement-scoped rows (ADR-102). |
| `Resource.firm(tenant_id)`, `Resource.engagement(tenant_id, id, archived=...)` | What an action is done to; `archived` comes from the engagement row, never a literal (AUTHZ-003). |
| `ctx.tenant` | The `TenantContext` for `tenant_session` and `uow`. |

## Rules

- A route that returns a success without calling `authorise`/`visible` for its declared action becomes a 500. Check before writing: the guard runs after the handler, so it can't undo a committed write.
- Tokens prove identity only (ADR-029). Firm and engagement roles come from the database on every request; memberships aren't cached, so revocation applies to the next request.
- With several memberships the client sends `X-Abacus-Tenant`; it counts only if it matches an active membership (ADR-002).
- Matrix conditions not modelled yet (`in_scope`, `firm_setting(...)`, `assigned_only`, `client_visible_only`, `task_scope`) deny. Walls (ADR-026), client grants and agent scope come with their own tasks.
- `authz/_matrix.py` is generated from `docs/architecture/permission-matrix.yaml`: `python -m abacus_tools.codegen.permission_matrix`. Tests fail when they drift.
- Wiring a module's routes: its `api.py` exports an `AbacusRouter` named `router`, and `abacus/api/app.py` lists it in `ROUTERS`. Pattern: `docs/architecture/reference/tenancy-and-authz.md`.
- Not wall-safe: ethical walls (ADR-026) aren't modelled. Walls gate the first real firm (founder, 2026-10-06).
- Static rules:
  - UOW-003: only `repository.py` uses the `abacus_identity` engine.
  - AUTH-001: only `tokens.py` imports token libraries.
  - AUTH-002: only `service.py`/`routing.py` read the Authorization header or use `fastapi.security`.
  - AUTHZ-001: no role-name comparisons outside `authz/`.
  - AUTHZ-002: no `.firm_role` reads outside identity.
  - AUTHZ-003: no literal `archived`.
  - TENANT-002: only `service.py`/`routing.py` read the tenant header.
  - ROUTE-001: no other way to serve HTTP.
  - ROUTE-002: `SELF` only for `/v1/me`.
  - CTX-001: `AuthContext` is built only by `service.py`, and never copied with changes.

## Data

`users` is global; only `abacus_identity` (BYPASSRLS, read-only, a few columns) reads it, before a tenant is chosen. `firms`, `memberships` and `engagement_members` are tenant tables the app may only read for now.
