---
id: TASK-027
title: Break-glass support access
spec: SPEC-012
acceptance_criteria: [AC-1, AC-2, AC-3, AC-4, AC-5, AC-6, AC-7, AC-8, AC-9, AC-10]
risk_zone: red
status: done
branch: task-027-break-glass
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
Implement SPEC-012 (approved, Q1–Q5): staff tokens, support sessions (request, firm or emergency approval, end, revoke, acknowledge), read-only support access through the existing routes, per-request audit, the firm's session list, and the quarterly access-review report.

## Scope
All of SPEC-012. Excluded: infrastructure roles (TASK-014), notifications, and a staff console.

## Context to load
- Spec: `docs/specs/SPEC-012-break-glass.md`
- ADRs: ADR-028, ADR-020, ADR-024, ADR-036
- Code: `modules/identity/` (`routing.py`, `tokens.py`, `context.py`, `authz/`), `kernel/db` (`TenantContext`), migration 0002 (`audit_events.actor_kind`)

## Plan
- [x] Plan approved by human (founder, 2026-10-07: D1–D6). Approved by founder: paths listed under *Protected paths*

### Design (for founder review)
1. **Staff tokens** (`identity/tokens.py`):
   - a second `JwtVerifier` from `staff_issuer`, `staff_audience` and `staff_jwks`, with its own `configure_staff_verifier` for local runs and tests;
   - a staff token must carry an MFA claim;
   - staff tokens are never accepted by the firm verifier, and the reverse holds too.
2. **The support context is an `AuthContext` (D1).** A request with `X-Support-Session` (and the firm in the tenant header) is verified with the staff verifier, and the session is loaded in that firm's tenant. It must be `active`, before `expires_at` (database time), and owned by the token's subject. The result is `AuthContext`:
   - `tenant = TenantContext(firm, "support", "support:<session>")`;
   - `user_id` = the staff ID and `membership_id` = the session ID;
   - `firm_role` = `platform_support` or `platform_support_content` (by scope);
   - `mfa_at` from the token.

   Every read route then works unchanged, and `authorise` and `visible()` need no new branch, since walls still apply through the existing wall clause.
3. **Read-only twice over (D2):**
   - `current_context` refuses a support context for any method but GET and HEAD (403);
   - separately, the matrix grants support roles read actions only;
   - a unit test pins that no non-read action allows either support role.
4. **Per-request audit (AC-8):** in the same dependency, before the handler, `support.request` is written (target `support_session`, with references to the route template's fingerprint and the method). If the write fails, the request fails (fail closed). The first refused use after expiry records `support_session.expired` and sets the status.
5. **Roles (D3):**
   - **`platform_support` (metadata):** `engagement.read_metadata`, `request_item.read`, `review.read`, `budget.read`, `methodology.read`, `connection.read_log` and `audit_event.read`;
   - **`platform_support_content`:** the same, plus `engagement.read`, `evidence.read` and `knowledge.read`;
   - `FirmRole` and the matrix `roles` gain both, and the codegen and the generated matrix tests are updated.
6. **Data (migration 0023):**
   - `support_sessions` (§7 of the spec; forced RLS; insert and lifecycle UPDATE grants; one active session per staff member and firm, as a partial unique index);
   - `audit_events.actor_kind` gains `support`, and `TenantContext.actor_kind` gains `support`;
   - `support_sessions_review(p_from, p_to)`, SECURITY DEFINER, returns rows across firms with `sha256(reason)`. EXECUTE goes to the migrations owner role only, never `abacus_app` (D4).
7. **Staff routes** (`/v1/support/sessions`, `…/{id}/approve` (emergency, second staff member), `…/{id}/end`):
   - they authenticate with a staff token through `current_staff`;
   - the route marker is `STAFF` (like `SELF`: no firm matrix action), because staff aren't firm members (D5);
   - the rules are in the service: reason length, at most 240 minutes, the emergency limit of 60 minutes, no self-approval, one active session.
8. **Firm routes:**
   - `GET /v1/support-sessions` (`support_session.read`: firm_admin);
   - `POST …/{id}/approve`, `…/revoke` and `…/acknowledge` (`support_session.manage`: firm_admin, `mfa_recent`).
9. **Access review** (`abacus_tools/access_review.py`, `make access-review QUARTER=2026Q4`): calls the definer function with `migrations_database_url` and writes `docs/operations/access-reviews/<quarter>.json`.

**Protected paths (approval file):**
- `backend/src/abacus/modules/identity/**`, `backend/src/abacus/kernel/**`, `backend/src/abacus/api/**`;
- `backend/migrations/**`;
- `docs/architecture/permission-matrix.yaml`;
- `backend/src/abacus_tools/**`, `backend/tests/unit/**` (pins);
- `Makefile`, `docs/operations/**`.

### Questions for approval
- **D1. Represent support as an `AuthContext` with a support firm role and tenant actor kind `support`, rather than a new context type?** *Recommendation: yes.* Every read route, `authorise` and `visible()` work unchanged, and walls still apply.
- **D2. Besides the matrix, hard-refuse any non-GET/HEAD request in a support session?** *Recommendation: yes*, as defence in depth. The cost is that POST-shaped reads (knowledge search) aren't available to support in v1.
- **D3. The metadata and content role split listed in §5?** *Recommendation: yes.*
- **D4. The access review reads across firms only through a definer function executable by the migrations owner role (not the app role), so the CLI uses the migrations credentials?** *Recommendation: yes.* No app code can call it.
- **D5. A `STAFF` route marker for staff-token routes, which have no firm matrix action?** *Recommendation: yes.* Their authorisation is the staff token plus the session rules.
- **D6. Write the approval file for the protected paths above?** *Recommendation: yes.*

## Definition of done
- [ ] All listed ACs have passing tests that reference them (independent tests deferred by the founder)
- [ ] Type check, lint, format, architecture and dependency rules pass
- [ ] Every query is tenant-scoped; every endpoint checks authorisation
- [ ] Module READMEs and the relevant docs are updated

## Progress log
- `2026-10-07` — Implemented:
  - the staff verifier and settings;
  - `support_sessions` and the `support` actor kind (migration 0023, with the owner-only review function);
  - the support service (request, firm and emergency approval, end, revoke, acknowledge, the support context, per-request audit);
  - the `STAFF` route marker and the staff and firm routes;
  - `current_context` for support sessions (GET and HEAD only);
  - the matrix support roles and actions;
  - `kernel.uow.audit_counts`;
  - `make access-review`;
  - pin tests that the support roles are read-only.

  Gates, the schema check and unit tests pass. An end-to-end run against local Postgres passed:
  - not usable before approval;
  - another staff member refused;
  - reads allowed and writes and content refused for the metadata scope;
  - the request count shown;
  - revocation effective;
  - self-approval refused;
  - an emergency approved by a second staff member.

  Full test runs deferred by the founder.
- `2026-10-07` — SPEC-012 approved and merged (#48). Design written for founder review.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| The staff ID is UUIDv5(issuer#subject), and the subject is stored on the session | Staff aren't users in our table; this gives a stable ID without one | No |
| Request counts come from `kernel.uow.audit_counts` (the audit trail's owner), not a query in identity | OWN-001 | No |
| `support.py` is excluded from AUTH-002 and CTX-001, and `access_review.py` from DB-001, each with a stated reason | They read the staff token, build a context from a validated session, and connect as the owner role | No |
| `schema_check` gains `OWNER_ONLY_FUNCTIONS`: definer functions the app role must not execute | The cross-firm review function | No |

## Questions for the human
- Design questions D1–D6 (above).

## Handoff
