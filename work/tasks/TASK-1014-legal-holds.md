---
id: TASK-1014
title: Legal holds — legal_holds and reference-counted hold_objects, LegalHoldApply and LegalHoldRelease, inheritance, the fail-closed hold check, routes (Q-02-T29)
spec: SPEC-051
acceptance_criteria: [AC-2]  # SPEC-051 (as TASK-965); the Q-02 epic ACs proved here: AC-34 to AC-37
risk_zone: red
status: done
epic: Q-02
plan_key: Q-02-T29
branch: s6-legal-holds
created: 2026-10-24
updated: 2026-10-24
---

## Objective
"With two overlapping holds, lifting one leaves every object held, a new upload into a held scope is held, and an unregistered hold check refuses the purge." Q-02 AC-34 to AC-37; ADR-033; DEC-71 / P-14.

## Plan (red zone)
- **Migration** `0126_legal_holds.py` (down_revision 0125): `legal_holds` (scope shape and release shape CHECKs, forward-only status trigger, `placed_by`/`released_by` bound to the session's human actor), `hold_objects` (PK hold × version, stamps once), `active_hold_count(uuid)`. App: insert columns and status columns only; no delete. Rollback: `alembic downgrade 0125`.
- **Storage port** (`evidence/storage.py`): `set_legal_hold(stored, on=)` and `legal_hold_on(stored)`. No fake exists in the repo: tests run against the compose S3 gateway (versitygw), which supports object legal holds.
- **Kernel slot** `kernel/holds.py`: `register_hold_check`, `held_versions`, `erasable_versions`, `HoldCheckMissing` (fail closed).
- **Evidence:** `holds.py` (place, lift, list through `visible_clients`, `holds_covering`, `inherit_holds`, batch steps), `hold_routes.py` (`GET/POST /v1/legal-holds`, `POST /v1/legal-holds/{id}/release`), `hold_activities.py`, `hold_runs.py` (starts from the outbox, the inheritance consumer), `workflows.py` (`LegalHoldApply`, `LegalHoldRelease`), `workflow_types.py`, `events.py`, `registry.py`; `service.add_version` calls `inherit_holds`.
- **Engagements:** `hold_scope.py` (engagements in a client or tax-year scope, an engagement's years, a work item's engagement), exported from `api.py`.
- **Notifications:** `legal_hold.placed` → `legal_hold_placed` (notify list and partners in scope; staff not walled).
- **Contract:** `docs/contracts/legal-holds.md` v1; register row. `make regenerate`; error codes.
- **Tests:** `tests/integration/test_legal_holds.py` (AC-34 to AC-37), `tests/unit/kernel/test_holds.py`, `tests/workflows/test_legal_holds_replay.py` with v1 histories (`abacus_tools.workflows.record_legal_holds`), the catalogue fan-out unit test; closed-list expectations extended (schema update columns, worker routing, catalogue).

## Progress log
- 2026-10-24: Built and tested. The plan's storage fake does not exist; S3 calls are tested on the compose gateway. Audit `Ref` takes identifiers and integers only (a code string raised), fixed. Records DEC-228, DEC-229.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-228 | Counting, scope semantics, shared stored objects, lift only when active, events, the slot's home | No (ADR-033 holds) |
| DEC-229 | Purge, reconciliation and IAM are later rows | No |

## Human to-dos
- When the `s3-evidence` module and the app/worker role policy are written (Q-01, with TASK-968): allow `s3:PutObjectLegalHold` and `s3:GetObjectLegalHold` on `arn:aws:s3:::<evidence bucket>/tenants/*`. No Terraform plan or apply was run.

## Verification (2026-10-24)
- `uv run pytest tests/integration/test_legal_holds.py tests/integration/test_evidence.py tests/integration/test_retention_object_lock.py tests/integration/test_retrieval.py tests/integration/test_notification_email.py tests/integration/test_human_only_guard.py tests/workflows/test_legal_holds_replay.py tests/unit/kernel/test_holds.py tests/unit/notifications tests/unit/worker tests/unit/quality/test_fresh_mfa_actions.py`: 328 passed.
- `tests/security/test_route_introspection.py` and `tests/integration/test_schema_check_db.py`: green after adding the two tables' update columns to the contract expectation; `tests/security/test_tenant_isolation.py -k "legal_holds or hold_objects"`: 2 passed.
- Pre-existing on `origin/main`, unrelated: `tests/contracts/c5_requests_binders/test_c5_consumer_r01.py::test_r01_every_client_reach_of_the_request_filter_needs_client_visible` (expects the pre-DEC-211 SQL shape, like the identity unit cases in TASK-1013).
