---
id: TASK-028
title: In-app notifications
spec: SPEC-013
acceptance_criteria: [AC-1, AC-2, AC-3, AC-4, AC-5, AC-6, AC-7, AC-8, AC-9, AC-10]
risk_zone: amber
status: awaiting-plan-approval
branch: task-028-notifications
worktree:
created: 2026-10-08
updated: 2026-10-08
---

> **Rules for the agent working this task**
> - Read this whole file before doing anything. Continue from the *Handoff* section if it has content.
> - Load only the files listed under *Context to load*, plus what the plan requires.
> - Amber and red tasks: do not write code until the plan is marked approved.
> - If scope must change, **stop** and add it to *Questions for the human*.
> - Never mark `done` until every item in *Definition of done* passes.
> - Append to the *Progress log* before ending any session, even mid-task.

## Objective
Implement SPEC-013 (approved, Q1–Q5): a new `notifications` module, a catalogue of six event kinds, idempotent fan-out from the outbox relay, own-only reads with read-time walls, the `notify` obligation (engagement self-join), and a 180-day purge.

## Scope
All of SPEC-013. Excluded: email, preferences, the SPA bell, and client users.

## Context to load
- Spec: `docs/specs/SPEC-013-notifications.md`
- ADRs: ADR-024, ADR-018, ADR-101, ADR-106
- Code: `kernel/uow` (emit and outbox), `worker/__main__.py` (`MODULES`, `SUBSCRIPTIONS`), `identity` (`authorise` notify, team, the support service, routing markers), `evidence/service.py` (`assign`), `ai_gateway/budgets.py`

## Plan
- [ ] Plan approved by human

### Design (for founder review)
1. **The module** `modules/notifications/` (`api.py`, `catalogue.py`, `service.py`, `repository.py`, `routes.py`, `models.py`, `README.md`):
   - BOUND-002 lets it depend on identity and engagements, and nothing imports it (it only subscribes);
   - AGENTS.md's module map and ADR-101's list of twelve modules become thirteen (Q5, a protected docs change).
2. **Events**, emitted in each producer's existing unit of work:
   - `support_session.requested` and `support_session.emergency_approved` (identity: `SupportSessionRequested` and `SupportSessionEmergencyApproved`, carrying the session ID);
   - `engagement.member_self_joined` (identity, see 6);
   - `review.assigned` (evidence: `ReviewAssigned`, carrying the engagement, the version and the assignee);
   - `budget.soft_crossed` and `budget.anomaly` (ai_gateway, D2):
     - the soft-limit alert opens a small unit of work in the firm's tenant (system actor), audits `budget.soft_crossed` and emits `BudgetSoftCrossed` (level, engagement);
     - the anomaly job does the same per flagged engagement in its tenant (`BudgetAnomaly`).
3. **The catalogue:** `kind → (event_type, recipients(event) → user IDs, engagement_id(event), subject)`. Recipients come from the APIs:
   - firm admins: identity `firm_admins(tenant)` (new);
   - an engagement's partner and managers, or the whole team: identity `engagement_team`, with a system-context variant `team_of(tenant, engagement_id)` (new);
   - the assignee, from the event.
4. **Fan-out:**
   - one relay subscription per catalogued event type, registered in `notifications.api.SUBSCRIPTIONS`, with the worker's `MODULES` gaining notifications;
   - the handler inserts with `ON CONFLICT (tenant_id, event_id, recipient_user_id) DO NOTHING` in one unit of work, audited as `notification.created` (one event per batch, with the count) because the unit of work needs one.
5. **Reads:**
   - **`OWN` route marker** (Q3, in identity routing): uses `current_context`, needs no matrix action, and the guard skips the authorise check. The service always filters `recipient_user_id = ctx.user_id`, and FLAG-style lint isn't needed because the queries live in one repository.
   - **Routes:**
     - `GET /v1/notifications?unread&limit&before`, returning items (`id`, `kind`, `engagement_id`, `subject_type`, `subject_id`, `created_at`, `read`) and `unread_count`;
     - `POST /v1/notifications/{id}/read` and `POST /v1/notifications/read-all`.
   - **Walls:** engagement-scoped rows are filtered with `visible(ctx, "engagement.read_metadata", engagement_id)` (or a null engagement).
   - **Support contexts:** they get 403 on these routes; staff never receive notifications.
6. **Self-join** (AC-8, D1): `POST /v1/engagements/{id}/self-join` in identity, beside the team functions:
   - `authorise(engagement.self_join)`;
   - add the admin to the team as `reviewer` (content read, no decisions: the matrix's reviewer row);
   - audit `engagement_member.self_joined`;
   - emit `EngagementMemberSelfJoined`.

   `authorise` stops denying `notify` obligations and instead requires the caller to emit (documented). The obligation is now met by the only action that carries it.
7. **Templates** (AC-7): `catalogue.TEMPLATES[kind]` are fixed English strings with named placeholders, exposed as `kind` only in the API. The SPA renders them later, and a unit test pins that every kind has a template.
8. **The purge:** a daily task beside the anomaly job in the worker runs a SECURITY DEFINER function `notifications_purge(p_days)` (cross-tenant, owner-reviewed, executable by `abacus_app`) and logs the count.
9. **Migration 0024:** `notifications` (forced RLS; insert grants; UPDATE `read_at` only; a unique (`tenant_id`, `event_id`, `recipient_user_id`); index (`tenant_id`, `recipient_user_id`, `created_at`)) and the purge function, plus the schema maps.

**Protected paths (approval file):**
- `AGENTS.md`, `docs/adr/ADR-101-namespaced-backend-layout.md` and `docs/architecture/permission-matrix.yaml` (if needed);
- `backend/src/abacus/modules/{notifications,identity,evidence}/**`, `backend/src/abacus/ai_gateway/**`, `backend/src/abacus/worker/**` and `backend/src/abacus/api/**`;
- `backend/migrations/**`;
- `backend/src/abacus_tools/**` and `backend/tests/unit/**` (pins).

### Questions for approval
- **D1. Self-joining admins join as `reviewer` (they read content but can't accept or reject; the matrix gives reviewers neither)?** *Recommendation: yes.* ADR-024 says admins join to see content, not to decide.
- **D2. Budget alerts become audited events (`budget.soft_crossed`, `budget.anomaly`) with domain events, written by the gateway as the system actor in the firm's tenant?** *Recommendation: yes.* Notifications need an event, and the alert is worth auditing anyway.
- **D3. Write the approval file for the protected paths above?** *Recommendation: yes.*

## Definition of done
- [ ] All listed ACs have passing tests that reference them (independent tests deferred by the founder)
- [ ] Type check, lint, format, architecture and dependency rules pass
- [ ] Every query is tenant-scoped; every endpoint checks authorisation
- [ ] Module READMEs and the relevant docs are updated

## Progress log
- `2026-10-08` — SPEC-013 approved and merged (#50). Design written for founder review.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|

## Questions for the human
- Design questions D1–D3 (above).

## Handoff
