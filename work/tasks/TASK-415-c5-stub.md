---
id: TASK-415
title: C5 v1 stub, BND/SHL-14 family - models, route stubs (incl. portal mark-done, ignore, upload intents, withdraw), matrix rows, binders.engine flag, firm-setting keys, contract doc, SPEC outline; ADR-137 acceptance check (P-06-T01)
spec: SPEC-319
acceptance_criteria: [AC-1, AC-2, AC-3, AC-4]
risk_zone: red
status: done
epic: P-06
plan_key: P-06-T01
branch: p06-t01-c5-stub
created: 2026-10-22
updated: 2026-10-22
---

## Objective
"Merges with the flag off, generated client types, and a contract doc listing every human-only action and audit event."

## Plan (red zone)
- **Files:** `requests/contract.py` and `evidence/contract.py` (models and 501 stubs), the two modules' `api.py` (ROUTERS), `permission-matrix/requests.yaml` and `evidence.yaml`, `feature-flags/requests.yaml` (new), generated files through `make regenerate`, `docs/contracts/c5-requests-binders.md`, `docs/contracts/README.md`, SPEC-319, DEC-136.
- **Migrations:** none (P-06-T05 owns `binder_engine`).
- **Tests:** `backend/tests/contracts/c5_requests_binders/test_c5_stub.py` (AC-1 to AC-4); the generated matrix test covers the new rows.
- **Rollback:** revert the commit; nothing reads the new routes and the flag is off.

## ADR-137 acceptance check (fallback finalisation)
The plan's "ADR-137" for P-31 is **ADR-162** (`docs/adr/backlog.md`: ADR-137 is the module map). `docs/adr/ADR-162-client-withdrawal-unaccepted-uploads.md` is `status: accepted`, dated 2026-10-22, deciders notanaskhan and ayushkbhatia, and records the detached-key erase mechanism, the 30-day window and that accepted evidence is never withdrawable. The R1 fallback (T01 finalising it) is not needed. The withdraw stub follows ADR-162 §3 (route, action, Idempotency-Key, roles).

## What changed
- **Routes (all 404 with `binders.engine` off, 501 `not_implemented` on; no seed-derived fixtures yet: `stub_from_seed` does not exist, the binder slice is P-06-T08):**
  - `/v1/binders`: `GET` index (`binder.read`), `POST` create (`binder.create`), `GET /{id}` (`binder.read`), `GET /{id}/requests` and `/live` (`request_item.read`), `POST /{id}/publish` + Idempotency-Key, `/publish/undo`, `/unpublish` (`binder.publish`), `POST /{id}/duplicate` (`binder.create`), `PUT /{id}/recipients` and `/follow-up-override` (`binder.update`), `GET /{id}/client-preview` (`binder.read`), `GET /{id}/activity` (`activity.read`).
  - `/v1/engagements/{eid}/request-items/{id}`: `PATCH` and `DELETE` (`request_item.update`), `POST /send` + Idempotency-Key and `/send/undo` (`request_item.send`), `/waive` (`request_item.waive`), `/return-to-client` + Idempotency-Key (`request_item.return`), `/delegate` (`request_item.delegate`), `/incorporate` (`request_item.update`), `GET /activity` (`activity.read`).
  - `/v1/portal`: `POST /binders/{id}/mark-done` (`binder.mark_done`), `POST /request-items/{id}/ignore` (`request_item.ignore`), `POST /request-items/{id}/upload-intents` (`evidence.upload`).
  - `POST /v1/engagements/{eid}/evidence-versions/{vid}/withdraw` + Idempotency-Key (`evidence.withdraw`; behind `binders.engine` until T19 creates `evidence.withdrawal`).
  - Not duplicated: the live create, client-visibility, client-assignee, client-view, SPEC-042 client-response and client-done routes, and the evidence decision routes.
- **Matrix (§4.4):** new `binder.read`, `binder.create`, `binder.update`, `binder.publish`, `binder.mark_done`, `request_item.send`, `request_item.return`, `request_item.ignore` (reason required), `request_item.delegate`, `evidence.withdraw`; `evidence.accept`/`reject` + staff `firm_setting(staff_can_accept_evidence)` (DEC-37). Every human-only action has `agent: deny`. `request_item.create` + staff is left to P-06-T10 (live route; DEC-136). The SHL-20 rows (`screening.feedback`, `follow_up.*`) are P-06-T15's.
- **Flag:** `binders.engine` (boolean, default false, owner notanaskhan, created 2026-10-22, expires 2027-01-20).
- **Firm-setting keys:** §4's three keys are already registered by F-03-T24 under `seniors_can_publish`, `client_service_can_publish` and `staff_can_accept_evidence` (migration 0081's CHECK). No new key; the mapping is DEC-136.
- **Decisions:** DEC-136 (OQ-1 decided as recommended, mechanism in T07 because conditions only narrow; key names; portal ignore vs SPEC-042; staff create deferred).
- **Docs:** `docs/contracts/c5-requests-binders.md` (routes, models, status words, human-only actions, errors, audit and outbox events), C5 register row `stub`, SPEC-319 outline.
- **Generated:** `_matrix.py`, `_flags.py`, `actions.gen.ts`, the generated matrix test, `openapi.json` and the api-client. The generated route inventory `tests/security/test_route_introspection.py` lists the 26 new routes. No error code is added (`error-codes.yaml` unchanged).

## Hand-off: what P-06-T05 must add for these routes to go live
`request_lists`: `unpublished_at/by`, `unpublish_reason`, `created_from`, `template_ref`, `follow_up_override`, `closed_at`, `closed_reason`; `binder_recipients`. `request_items`: `title`, `category_id`, `firm_owner_user_id`, `period_start/end`, `wave`, `kind`, `source_tag`, `supports_ref`, `linked_ref`, `drafted_by_run_id`, `drafted_wording_source`, `drafted_wording_fingerprint`, `sent_by`, `deleted_at/by`, plus somewhere to keep the client's ignore reason (0071 has only `client_ignored_at`; reuse SPEC-042's insert-only `client_item_responses` or add a column). New `request_delegations`, UNLOGGED `request_upload_intents`, `binder_activity`. The seed must turn `binders.engine` and the three firm settings on for Brightwater Hale (T05 `seed_dev.py` / T08). The withdraw route needs T18's `evidence_withdrawals` and `evidence_object_keys`.

## Progress log
- 2026-10-22: built on `origin/main` at 91264d4, rebased on 7b31f56 (SPEC-318 and DEC-135 were taken on main meanwhile: renumbered to SPEC-319 and DEC-136; generated files resolved by `make regenerate`; route introspection 338 passed). `make regenerate`, `make check-generated` clean. `tests/contracts/c5_requests_binders` 48 passed; generated matrix test `-k "binder or request"` 294 passed; `test_openapi`, `test_allowed_actions`, `test_policy_overrides`, `test_agent_principal` 88 passed. `tests/unit/identity/test_permission_matrix.py` has 5 failures that are not from this change (role partition misses `firm_partner` from DEC-132, and `firm.read_settings` cases hit asyncpg loop errors without a database). ruff, pyright clean on touched files.
