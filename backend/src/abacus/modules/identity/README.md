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
| `register_independence(column, lookup)` | Called once by `engagements.api`: whether a person has confirmed their independence for an engagement (SPEC-025, TASK-045). Unregistered means refused. |
| `ctx.tenant` | The `TenantContext` for `tenant_session` and `uow`. |

## Rules

- A route that returns a success without calling `authorise`/`visible` for its declared action becomes a 500. Check before writing: the guard runs after the handler, so it can't undo a committed write.
- Tokens prove identity only (ADR-029). Firm and engagement roles come from the database on every request; memberships aren't cached, so revocation applies to the next request.
- With several memberships the client sends `X-Abacus-Tenant`; it counts only if it matches an active membership (ADR-002).
- Matrix conditions not modelled yet (`in_scope`, `firm_setting(...)`, `assigned_only`, `client_visible_only`, `task_scope`) deny. Client grants come with their own task.
- `authz/_matrix.py` is generated from `docs/architecture/permission-matrix.yaml`: `python -m abacus_tools.codegen.permission_matrix`. Tests fail when they drift.
- Wiring a module's routes: its `api.py` exports an `AbacusRouter` named `router`, and `abacus/api/app.py` lists it in `ROUTERS`. Pattern: `docs/architecture/reference/tenancy-and-authz.md`.
- Ethical walls (ADR-026, SPEC-002) are checked in `authorise` before roles and in every `visible()` filter, for the user, the person an agent's run was started by, or the person a system run acts for. A walled engagement answers 404, not 403. The walled clients are read once per request and live on every step outside one. A firm admin can't lift a wall on themself (409 `own_wall`). `WALL_SAFE` is true, so production may start.
- Independence (SPEC-025 AC-7, per person; TASK-045): actions marked `independence: required` in the matrix (evidence read, upload, accept and reject; review read, take and assign; "Screen now"; the connection access log) are granted by a staff engagement role only once that person has confirmed their independence for the engagement. `authorise` checks it after roles (layer `independence`, logged, never shown) and `visible()` adds it to the staff-role membership filter. Firm and client roles, break-glass support and system runs aren't bound; an agent is, through its initiator. Firm-level reads leave it to `visible()`, row by row. The answer is read once per request.
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

## Break-glass support (SPEC-012; TASK-027)
Platform staff have no standing access (ADR-028). Staff sign in with a separate issuer (`staff_*` settings; MFA required) and are never firm members.

**Requesting:** `POST /v1/support/sessions` (staff token, route marker `STAFF`) requests a session for one firm, with a reason, a scope (`metadata` or `content`) and a duration of at most 240 minutes.

**Approving:**
- normally a firm admin with fresh MFA approves it (`/v1/support-sessions/{id}/approve`);
- for an emergency, a second staff member does (`/v1/support/sessions/{id}/approve`), the session lasts at most 60 minutes, and it is flagged to the firm until acknowledged.

**During the session:** requests with the staff token and `X-Support-Session` (plus the firm in `X-Abacus-Tenant`) become an `AuthContext`:
- the firm role is `platform_support`, or `platform_support_content` for the content scope;
- the tenant actor kind is `support`;
- only GET and HEAD are allowed, and the matrix grants these roles read actions only;
- each request is audited (`support.request`) before it runs, and a failed audit refuses it.

**Ending it:** firm admins list sessions, revoke one, and acknowledge emergencies. Staff end their own. `make access-review QUARTER=…` (owner role) writes the quarterly SOC 2 report.

## Firm-level reads by engagement role (SPEC-014; TASK-029)
On a firm-level resource (`Resource.firm`), a **read** action counts the person's engagement roles on the firm's non-archived engagements, as well as their firm role.
- The non-archived engagements come from a subquery the engagements module registers (`register_active_engagements`).
- The lookup is skipped when the firm role already allows the action, cached per request, and fails closed.
- Only `allow` grants; conditional decisions and firm-level writes are unchanged.
- Support contexts, agents and system contexts never gain engagement roles here.

## Client users and invitations (SPEC-015; TASK-030)
Members are `staff` or `client` (`memberships.kind`). A client membership has no firm role, and client engagement roles (`client_admin`, `client_contributor`) belong only to client memberships, enforced by a trigger.

**The token:**
- An invitation stores no token.
- On `client_invitation.issued`, communications calls `issue_invitation_token`, which keeps only the SHA-256 in `invitation_tokens`, and emails the link (`#token=…`).
- A resend issues a new token, and the old one stops working.

**Accepting:** `POST /v1/invitations/accept` (route marker `IDENTITY`) needs only a verified identity whose provider-verified email matches the invitation.
- Users and client memberships are created only by the definer functions `provision_client_user` and `add_client_membership`.
- Every failure is the same 404.
- 10 failures in an hour lock the identity for 15 minutes.

**Managing contacts:** firm partners and managers invite, list, revoke, resend and remove (`/v1/engagements/{id}/client-…`). Client admins manage contributors only.

## Engagement team (SPEC-017; TASK-032)
`team.py` (called by engagements after `lock_ref` and `authorise`):
- **Candidates:** active staff, not on the team, not walled from the client.
- **Changes:** add, change role and remove.
- **Managers** handle seniors, staff and reviewers only.

Role changes and removals go through the definer functions `team_member_set_role` and `team_member_remove`, which keep at least one engagement partner (409 `last_partner`).

On removal, the hook that evidence registers (`register_member_removed`) releases the person's review assignments in the same unit of work. The person added is notified (`engagement_member.added`).

## Firm members picker (SPEC-019 Q4; TASK-034)
`GET /v1/firm/members` (`wall.create`) lists the firm's active **staff** members with names, never client users, for the walls screen's person picker. Engagements serves the matching client picker at `GET /v1/firm/clients`.

## Client conditions on request items (SPEC-020; TASK-035)
- **In `authorise`:** `Resource` may carry `ItemFacts` (`client_visible`, `client_assignee`). `client_visible_only` then allows a client-visible item; `assigned_only` allows a client-visible item assigned to the person. Without the facts both still deny.
- **For lists:** `visible_items` is the list-query twin. `authorise_items` lets a client list an engagement's items, which are then filtered row by row.
- **`visible()` counts client roles** the matrix allows (it agrees with `authorise`). Client roles read engagement metadata (their own engagements only).
- **Client contacts** now carry members' display names.

## Standing consent (SPEC-022 TASK-038 D3)
`member_context(tenant_id, user_id)` is an `AuthContext` for a live membership, with no MFA time.
- **Its use:** background work the platform starts on a person's standing consent (today only automatic retrieval, for the client admin who connected).
- **Fails closed:** it returns None once the membership is no longer active.
- **New callers need the founder's approval.**

## Self-serve sign-up (SPEC-024 AC-1; TASK-040)
- **Route:** `POST /v1/signup` (`IDENTITY`: a verified token with a provider-verified email, no membership) with `{code, firm_name}`.
- **Who:** someone already on a firm's staff is refused (`signup_already_staff`); that's read across firms through the identity role.
- **The reviewed definer `firm_signup`:**
  - rate-limits failures (5 an hour per identity, 20 per address), spends the founder-issued code, finds or creates the user, creates the firm and its first `firm_admin`;
  - records every attempt as fingerprints in `signup_attempts`.
- **Refusals:** `signup_code_invalid` and `signup_rate_limited` are logged; `firm.created` is audited in the new firm.
- **Codes:** issued by the founder with `python -m abacus_tools.signup_codes issue --note … [--days 30]` (shown once, stored as SHA-256), and listed with `list`.
- **The SPA:** a signed-in identity with no firm sees the no-firm page, with "Set up your firm"; a client-only person goes to their client home.

## People and firm roles (SPEC-024 AC-3, AC-4; TASK-041)
`staff.py`, all `firm.manage_users` (fresh MFA), listing included.
- **Invitations:** `/v1/firm/staff/invitations` (create, `/{id}/resend`, `/{id}/revoke`) with an email and a firm role or none.
  - 14 days, single-use; the token is issued at delivery (`StaffInvitationIssued`, emailed by communications with a `/join` link) and kept only as a hash in `staff_invitation_tokens`.
  - The client lockout (`invitation_failures`) is shared.
- **Accepting:** `POST /v1/invitations/staff/accept` (`IDENTITY`).
  - The verified email must match.
  - `add_staff_membership` refuses a client contact of the firm (409 `client_contact`) and reactivates a revoked member with the new role.
- **Roles and access:** `PUT /v1/firm/staff/{user_id}/role` and `POST …/{user_id}/revoke`, through definer functions that keep at least one active firm administrator (409 `last_admin`).
  - Revocation applies on the next request; engagement roles stay as history.
- **Listing:** `GET /v1/firm/staff`.
- **SSO:** held until the identity vendor is confirmed (TASK-040 amendment 4).

## Autonomy and onboarding facts (SPEC-024 AC-5, AC-7; TASK-042)
`firm_settings.py`.
- **Autonomy:** `firms.autonomy_level` (ADR-061; new firms at Routine, 1).
  - `GET /v1/firm/autonomy` (`firm.read_settings`).
  - `PUT /v1/firm/autonomy` (`autonomy_policy.update`, fresh MFA, audited); levels 2 and 3 are refused, 409 `level_not_available`.
  - `autonomy_level(tenant_id)` is read fresh by the platform's automatic actions: at Advise (0), automatic retrieval and automatic screening start nothing.
- **Onboarding facts:**
  - `firm_facts(ctx)` gives the checklist identity's facts (staff, pending invitations, walls, acknowledgements);
  - `acknowledge(ctx, step)` (`firm.manage_settings`) records "budget looks right", "no walls needed", "SSO skipped" or the dismissal;
  - `note_budget_reviewed(tx)` marks the budget step when a budget is saved.

## Member-added hook and the letter policy (SPEC-025; TASK-044)
- **Hook:** `member_hooks.register_member_added` is called from every way a person joins a team (engagements asks them to confirm independence).
- **Letter policy:** `firms.require_letter`, read with `GET` and set with `PUT /v1/firm/letter-policy` (`firm.manage_settings`), makes the engagement letter block client data.
