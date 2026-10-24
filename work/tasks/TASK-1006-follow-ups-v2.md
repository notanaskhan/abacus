---
id: TASK-1006
title: Follow-ups v2 — migration follow_ups_v2, template-composed drafts per contact, edit, human send with Undo, dismiss; follow_up_drafted and follow_up_sent kinds; P-4 draft-only; follow_up.send agent deny (P-06-T14)
spec: SPEC-319
acceptance_criteria: [AC-16, AC-17, AC-18, AC-19, AC-20]
risk_zone: red
status: done
epic: P-06
plan_key: P-06-T14
branch: s6-follow-ups
created: 2026-10-24
updated: 2026-10-24
---

## Objective
"Replay of the pre-change P-4 history passes and no code path lets the agent principal send a follow-up." P-06 §3.2 Story 2.2, §3.6 Story 6.2, §4.2 `follow_ups_v2`, §4.3 follow-up routes, §4.4, §4.8; DEC-74, DEC-24, DEC-79.

## What already exists (TASK-104, F-03-T16)
`agents/follow_ups.py` (P-4 drafts only, `draft_now`), engagement-scoped routes `/v1/engagements/{eid}/follow-ups…` (list, draft, preview, send, dismiss), `communications/follow_ups.py` (`send_follow_up` from a template constant in code), `FollowUps.tsx`. Missing: the migration, database templates, edit, server-side Undo, the cross-binder draft, the agent deny, the C16 kinds.

## Plan (red zone)
- **Migration `0121_follow_ups_v2`** (down_revision 0115, re-chained at merge): `follow_up_schedules` + `binder_id`, `recipient_contact_id`, `kind ∈ {overdue, chase, screening_return}` (default `overdue` for old rows), `template_key`, `body_sealed` (the person's edited body, SEAL), `body_fingerprint`, `edit_fingerprint`, `drafted_by_kind ∈ {person, agent}` (old rows `agent`), `sent_by`, `sent_at`, `not_before`, `undone_at`; column grants for the new insert and update columns; `follow_up_items.sequence` CHECK 1..4; **new** `follow_up_returns(tenant_id, follow_up_id, evidence_version_id, reason_code)` insert-only, tenant_table. Rollback: `alembic downgrade 0115` (drops the columns and table; refuses while a `screening_return` row exists).
- **Migration `0122_follow_up_human_only`**: redefines `abacus_human_only_actions()` with `follow_up.sent` (verb send); `human-only-actions.yaml` and the generated `_human_only_actions.py` follow. Rollback: the 0097 list.
- **Matrix** (`agents.yaml`): `follow_up.draft` + `client_service`; `follow_up.send` + `staff`, + `client_service`, `agent: deny` (DEC-74). The engagement agent's policy spec drops `follow_up.send` from its task scope (version 2). `make regenerate`.
- **Templates in the database** (`communications/templates.py`): the C16 whitelist gains `firm_name` and the body-only block `request_list` (one line per request, refused in a subject); keys `notification.follow_up_sent` (Reminder) and `notification.follow_up_sent.screening_return` (Return). No template text in code; the `TEMPLATE`/`SUBJECT` constants go.
- **Service** `agents/follow_up_drafts.py` (v2): `draft_for` (binder ids or request ids → one draft per client contact per engagement, each open client-visible request listed once, never one already waiting in a draft for that contact), `view`, `edit` (sealed, `edit_fingerprint`), `send` / `send_many` (human only; scope check, 409 `out_of_scope`; approval grant `not_before = +10 s`; `follow_up.sent` event held by it), `undo` (void the grant; back to drafted, `undone_at`), `dismiss`. Subscriber on `follow_up.sent` → `communications.deliver_follow_up` (only communications sends; `created_by` is the sender).
- **Requests read** `requests.api.follow_up_candidates`: open (`requested`, `returned`), client-visible, not deleted requests of the given binders or ids, through `visible()`, with each binder's current recipients.
- **Routes** (agents, behind `binders.engine`): `POST /v1/follow-ups/drafts`, `GET /v1/follow-ups/{id}`, `PATCH /v1/follow-ups/{id}`, `POST /v1/follow-ups/{id}/send` (Idempotency-Key), `POST /v1/follow-ups/send`, `POST /v1/follow-ups/{id}/undo`, `POST /v1/follow-ups/{id}/dismiss`. The SPEC-027 engagement routes stay and use the same composition (template from the database).
- **Notifications:** `follow_up.drafted` (the event, renamed from `reminders.drafted`) → kind `follow_up_drafted` (approval, in-app, the leads); kind `follow_up_sent` registered (its email is the follow-up itself, sent by communications). Legacy `reminders.drafted` stays registered for old rows.
- **P-4:** the workflow holds no business state; the tick's activity drafts. No `workflow.patched` marker is needed (DEC-220); the existing histories replay unchanged, and a test proves the P-4 path never reaches the send path.
- **Tests:** `tests/unit/agents/test_follow_up_drafts.py` (grouping, never repeated), `tests/unit/communications/test_templates_block.py`, `tests/integration/test_follow_ups_v2.py` (AC-16 to AC-20), updated `test_autonomy_condition.py`, `test_follow_ups_and_due_dates.py` (templates imported; staff may now send), schema check, human-only drift.

## Progress log
- 2026-10-24: plan written.
- 2026-10-24: built. Migrations 0121 (follow_ups_v2) and 0122 (human-only `follow_up.sent`); `agents/follow_up_drafts.py`, `follow_up_routes.py`; `communications/follow_ups.py` now composes from the database template (the code template constants are gone); `requests/follow_up_reads.py`; matrix, policy spec v2, C16 kinds. Scope check covers only the text a person adds (the composed body's platform link and previously sent request titles tripped the amount rule). Updated, as DEC-74 changes them: `test_autonomy_condition.py`, `test_agent_authz.py` (role, not delegation), `test_banned_patterns_agents.py` (send moves to DENIED), the SPEC-027 suite (template imported; staff now sends; `follow_up.*` audit actions), `test_app_gates.py`, `test_worker_screening.py`, `test_screening_contract.py`, `test_catalogue.py`, `test_schema_check_db.py`. Tests: unit 18,446 passed (5 pre-existing identity failures from DEC-211 on main, order-dependent); contracts 2,660 passed (1 pre-existing R-01 consumer failure on main); integration (touched files) 555 + 202 passed.
- Deferred: the screening-return send (returns + shared comment in one UoW) to P-06-T20/T22; a firm-level template override (C16 has platform defaults only).

- 2026-10-24: security review fixes (5): chase only Published binders (409 `binder_not_published`); scope-check each title and the person's text at draft and send; the SPEC-027 engagement route kept (FollowUps.tsx uses it) but hardened (option b: refuses binder drafts, checks the note, sends through the grant-held outbox); one open chase draft per contact (partial unique index in 0121, ON CONFLICT, read inside the UoW); state-aware allowed_actions and independence on follow_up.*. Failing tests first: 13 review tests failed on the unfixed code and pass now. Open: human-only guard for a `system` actor (cross-cutting trigger change); the scope checker reads bare form numbers as amounts.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-220 | Follow-ups v2 storage, templates, recipients, P-4 without a patch marker, the screening-return send deferred | No |
