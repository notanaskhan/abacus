# identity

Who someone is, which firm they act in, and what they may do. PROTECTED (red zone).

## Public interface (`api.py`)

| Name | Use |
|---|---|
| `AbacusRouter` | Every module's router. Each route declares `action=` (a matrix action, or `SELF` for `/v1/me`) and `response_model=`; authentication is attached automatically. |
| `current_context` | FastAPI dependency giving the `AuthContext` (tenant from a validated membership). |
| `authorise(ctx, action, resource, *, reason=None)` | The only permission check. Raises `Forbidden` (403). |
| `visible(ctx, action, engagement_id_column)` | Filter for list queries over engagement-scoped rows (ADR-102). |
| `Resource.firm(tenant_id)`, `Resource.engagement(tenant_id, id, archived=..., client_id=...)` | What an action is done to; `archived` and `client_id` come from the engagement row (`EngagementRef.resource()`), never a literal (AUTHZ-003). |
| `register_engagement_client(column, lookup)` | Called once by `engagements.api`: how to find an engagement's client, for walls. Identity never imports engagements (TASK-016 Q1). |
| `ctx.tenant` | The `TenantContext` for `tenant_session` and `uow`. |

## Rules

- A route that returns a success without calling `authorise`/`visible` for its declared action becomes a 500. Check before writing: the guard runs after the handler, so it can't undo a committed write.
- Tokens prove identity only (ADR-029). Firm and engagement roles come from the database on every request; memberships aren't cached, so revocation applies to the next request.
- With several memberships the client sends `X-Abacus-Tenant`; it counts only if it matches an active membership (ADR-002).
- Matrix conditions not modelled yet (`in_scope`, `firm_setting(...)`, `assigned_only`, `client_visible_only`, `task_scope`) deny. Client grants come with their own task.
- `authz/_matrix.py` is generated from `docs/architecture/permission-matrix.yaml`: `python -m abacus_tools.codegen.permission_matrix`. Tests fail when they drift.
- Wiring a module's routes: its `api.py` exports an `AbacusRouter` named `router`, and `abacus/api/app.py` lists it in `ROUTERS`. Pattern: `docs/architecture/reference/tenancy-and-authz.md`.
- Ethical walls (ADR-026, SPEC-002) are checked in `authorise` before roles and in every `visible()` filter, for the user, the person an agent's run was started by, or the person a system run acts for. A walled engagement answers 404, not 403. The walled clients are read once per request and live on every step outside one. A firm admin can't lift a wall on themself (409 `own_wall`). `WALL_SAFE` is true, so production may start.
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

`users` is global; only `abacus_identity` (BYPASSRLS, read-only, a few columns) reads it, before a tenant is chosen. `firms`, `memberships` and `engagement_members` are tenant tables the app may only read for now. `ethical_walls` is the app's to insert and to mark removed (forward-only; never deleted).
