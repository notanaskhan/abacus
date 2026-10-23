---
id: TASK-914
title: Binder lifecycle service and routes - create, read, publish with G3 and a grant-held Undo, unpublish, duplicate, recipients, mark-done, close, preview, activity (P-06-T07)
spec: SPEC-319
acceptance_criteria: [AC-5, AC-6, AC-7, AC-8, AC-9]
risk_zone: amber
status: done
epic: P-06
plan_key: P-06-T07
branch: p06-t07-binder-lifecycle
created: 2026-10-23
updated: 2026-10-23
---

## Objective
"Publishing before G3 answers 409 binder_gate_unmet except for intake binders, and Undo within 10 seconds leaves no email" (P-06-T07; SPEC-319 AC-5 to AC-9; ADR-161, DEC-24).

## Plan (amber)
- **Files.**
  - `requests/binders.py` *(new)*: the binder service.
  - `requests/repository.py`: a binder section.
  - `requests/models.py`: the 0070/0071/0100 columns mapped.
  - `requests/contract.py`: the routes named below call the service behind `binders.engine`. Shapes are unchanged. 404 when off, as before. The rest stay `_stub`.
  - `requests/roll_forward.py`: `copy_binder_items` for the prior-year create.
  - `requests/api.py`: `SUBSCRIPTIONS` for the close subscriber, plus empty `WORKFLOWS`/`ACTIVITIES`.
  - `requests/audit_targets.py`: the `binder` audit kind.
  - `engagements` `client_contact_names` and `organisations` `contact_facts`, for recipients.
  - `kernel/uow`: `audit_of_targets` and `audit_total_of_targets`, the narrow audit reads for binder activity and for Undo's grant lookup.
  - `abacus_tools` `LIST_EXEMPT`: four binder lookups made after `authorise`.
- **Routes implemented.**
  - `POST /v1/binders`: blank, template or prior-year.
  - `GET /v1/binders/{id}`, with `allowed_actions`.
  - `GET /{id}/requests`: grouped rows through `visible_items`.
  - `POST /{id}/publish`, with `Idempotency-Key`, G3 except `intake`, and `due_date_required`.
  - `POST /{id}/publish/undo`.
  - `POST /{id}/unpublish`.
  - `POST /{id}/duplicate`.
  - `PUT /{id}/recipients`.
  - `GET /{id}/client-preview`.
  - `GET /{id}/activity`.
  - `POST /v1/portal/binders/{id}/mark-done`.
- **Left as stubs.**
  - Index: P-06-T11.
  - Live poll and upload intents: P-06-T10.
  - Follow-up override: not named in this task.
  - Request-item lifecycle routes: P-06-T10.
  - Withdraw: P-06-T19.
- **Publish.** One `binder.published` outbox event (identifiers: binder, engagement, recipient contacts, items sent) held by an approval grant. The grant's `not_before` is business now + 10 s. Undo within the window voids the grant and writes the compensating rows, so the relay never delivers the event. After the window: 409 `undo_window_closed`. After the grant is consumed: 409 `effect_started`.
- **Registry, flags, matrix.** No changes. The actions and the flag exist (P-06-T01).
- **Module graph.** Unchanged. Recipient names and the client check go through a new `engagements.api.client_contact_names`, which uses a new `organisations.api.contact_facts`. Engagements already depends on organisations, so the plan's graph (pinned by `test_banned_patterns`) stays as it is.
- **Error codes.**
  - New: `binder_gate_unmet`, `binder_not_draft`, `binder_not_published`, `due_date_required`, `reason_required`, `undo_window_closed`, `effect_started`.
  - Rebuilt with `abacus_tools.quality.error_codes --write`. The kernel's `idempotency_key_invalid` and `idempotency_key_reused` now enter the catalogue too, since a route raises them.
- **Tests first.**
  - `tests/integration/test_binder_lifecycle.py` (Postgres) covers G3 and intake, due dates, publish then Undo with the relay delivering nothing, a late Undo, Undo after consume, an idempotent retry, unpublish, duplicate as part n, insert-only recipient history, mark-done, the client preview, close and activity.
  - The contract stub test moves the implemented routes from "501" to "404 only".
- **Rollback.** Revert the commit. There is no migration, and the routes stay behind `binders.engine` (default off).

## Decisions
- **No migration.** Gaps found:
  - 0071's `request_items_requested` trigger ties `draft`/`requested` to `client_visible`, so a client-visible request in a Draft binder already reads `requested`. Publish therefore stamps `sent_at`/`sent_by` on the binder's client-visible requests not yet sent ("items sent"), and Undo clears them. Client principals can't see a binder until it is published (INV-4, checked on `binder.read` and on every binder read), so nothing reaches the client before publish.
  - Moving item status `draft` to `requested` on publish (and back on Undo) needs that trigger redefined. Deferred to P-06-T10, which owns the request lifecycle.
- **Where Undo finds its grant.** The grant id is in the `binder.published` audit event's `after` reference. There is no grant column on `request_lists`.
- **Close.** C1 has no `work_item.status_changed` event in code yet. The subscriber handles that event type (payload `work_item_id`, `to_status`) and `engagement.status_changed` (`engagement_id`, `to_status`). It closes non-terminal binders when the status is `delivered` or `archived` (the default rule; `register_binder_close_rule` lets a kind add its own). It is audited `binder.closed` as `system`.
- **Template create.** Records `created_from = template` and `template_ref`. Seeding requests from a firm template waits for K-01's template store; no firm content goes in code.
- **Done count.** Requests the client has finished (`uploaded`, `received`, `not_applicable`) out of the client-visible ones. The open count at mark-done is the rest.
- **`reason_required`.** `UnpublishIn.reason` is required with `min_length=1`, so an HTTP request without one is refused by validation (422) before the service. The service still raises `reason_required` for a blank reason.

- **Client 404s.** A client principal denied a binder read or mark-done by the client conditions (a binder that isn't published, or a contributor with nothing in it assigned) gets 404, not 403 (INV-4). A firm person without a relationship still gets 403.
- **Unpublish inside the window.** It also voids the publish grant, so no "published" email follows an unpublish.
- **Undo of a republish.** It returns the binder to `unpublished`, recorded as `from_unpublished` in the publish's audit reference. The earlier `published_at` is not restored, because it was overwritten.
- **Contract transition.** The implemented routes no longer document 501. `test_c5_stub.py` now lists them in `IMPLEMENTED`; coverage is kept. `test_worker_screening.py` now expects `requests` among the worker's modules and the two status events among the routed handlers.

## Deferred
- **Index read model:** P-06-T11.
- **Live poll, upload intents, the request-item lifecycle routes, and item `draft`/`requested` moving on publish:** P-06-T10. The last one needs the 0071 trigger redefined.
- **Follow-up override:** not named in this task. Still a stub.
- **Template create:** seeding requests waits for K-01's template store.
- **C1 `work_item.status_changed`:** not emitted yet. The subscriber already handles it.
- **The email itself:** P-06-T06's delivery, which subscribes to `binder.published`.
- **Human-only register:** `binder.published` is not in `human-only-actions.yaml`. Adding it needs a migration. The matrix denies the agent, and only a person can be issued the grant.
- **Found, not fixed (outside this task):** SPEC-025's `copy_items` turns a rolled-forward item client-visible even when last year's wasn't, because new items default to `client_visible = true` (0028) and it only ever sets `true`. `copy_binder_items` sets `false` explicitly.

## Progress log
- 2026-10-23: plan written; tests first, then the service.
- 2026-10-23: `test_binder_lifecycle.py` (16) passes against Postgres. Also passing: the c5 contract tests, unit api/identity/quality/requests/worker, route introspection, and the engagements, evidence, approval-grant and relay integration suites.
  - ruff, pyright (touched files), banned_patterns, `make regenerate`/`make generate`/`make check-generated`: clean.
  - No new `abacus__` schema names.
  - On main, not from this change: `validate_docs` (duplicate TASK-434) and the secrets scan (`apps/web/.../portal.contract.test.ts`).
