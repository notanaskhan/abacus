# identity

Who someone is, which firm they act in, and what they may do. PROTECTED (red zone).

## Public interface (`api.py`)

| Name | Use |
|---|---|
| `AbacusRouter` | Every module's router. Each route declares `action=` (a matrix action, or `SELF` for `/v1/me`) and `response_model=`; authentication is attached automatically. |
| `current_context` | FastAPI dependency giving the `AuthContext` (tenant from a validated membership). |
| `authorise(ctx, action, resource, *, reason=None)` | The only permission check. Raises `Forbidden` (403). |
| `visible(ctx, action, engagement_id_column)` | Filter for list queries over engagement-scoped rows. |
| `Resource(tenant_id, engagement_id=None, archived=False)` | What an action is done to. |
| `ctx.tenant` | The `TenantContext` for `tenant_session` and `uow`. |

## Rules

- A route that returns a success without calling `authorise`/`visible` for its declared action becomes a 500. Check before writing: the guard runs after the handler, so it can't undo a committed write.
- Tokens prove identity only (ADR-029). Firm and engagement roles come from the database on every request; memberships aren't cached, so revocation applies to the next request.
- With several memberships the client sends `X-Abacus-Tenant`; it counts only if it matches an active membership (ADR-002).
- Matrix conditions not modelled yet (`in_scope`, `firm_setting(...)`, `assigned_only`, `client_visible_only`, `task_scope`) deny. Walls (ADR-026), client grants and agent scope come with their own tasks.
- `authz/_matrix.py` is generated from `docs/architecture/permission-matrix.yaml`: `python -m abacus_tools.codegen.permission_matrix`. Tests fail when they drift.
- Static rules: AUTH-001 (only `tokens.py` reads tokens), AUTHZ-001 (no role comparisons outside `authz/`), TENANT-002 (only `service.py` reads the tenant header), UOW-003 (only `repository.py` uses the `abacus_identity` engine).

## Data

`users` is global; only `abacus_identity` (BYPASSRLS, read-only, a few columns) reads it, before a tenant is chosen. `firms`, `memberships` and `engagement_members` are tenant tables the app may only read for now.
