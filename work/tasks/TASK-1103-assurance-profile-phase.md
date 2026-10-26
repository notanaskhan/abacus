---
id: TASK-1103
title: Migration assurance_profile_phase and the phase service - EBP plan kind, 103(a)(3)(C), record-mode moves, derived on gate.met, PATCH profile (A-01-T05)
spec: SPEC-330
acceptance_criteria: [AC-9, AC-10, AC-11, AC-12, AC-13, AC-14]
risk_zone: amber
status: done
epic: A-01
plan_key: A-01-T05
branch: s7-a01-audit-wedge
created: 2026-10-24
updated: 2026-10-24
---

## Objective
"Backward, skipped and agent phase moves are refused and a registered gate provider ends record mode for its phase."

## Plan (amber zone)
- **Migration** `0134_assurance_profile_phase` (down_revision `0133`): `assurance_work_items` + `ebp_plan_kind` (CHECK dc/403b/db), `limited_scope_103a3c`, `phase_source` (recorded/derived), `phase_changed_at`, `version`; column UPDATE grants; index `(tenant_id, phase, work_item_id)`. New insert-only `assurance_phase_events` (trigger + revoked UPDATE/DELETE, forced RLS, insert-column grants, CHECKs: recorded ⇒ human with a user, derived ⇒ system with a gate). The 0068 phase CHECK is kept (DEC-262). Rollback: `alembic downgrade 0133`.
- **engagements** (owner of the table): model columns, registry UPDATE_COLUMNS, `work_items.assurance_item`, `lock_assurance_item`, `move_assurance_phase`, `set_assurance_profile`; `slots.gate_registered`; exported through `engagements.api`.
- **assurance**: `phase_models.py`, `phase.py` (`record_phase`, `derive_phase`, `on_gate_met`, `update_profile`, errors `phase_backward`, `phase_skip`, `phase_follows_gate`, `phase_invalid`, `stale_version`), registry table, `api.SUBSCRIPTIONS` (`gate.met`), routes PATCH profile and POST phase live behind `audits.cockpit` (Idempotency-Key on the phase).
- **Closed lists:** worker modules and handlers (`test_worker_screening.py`), tenant-isolation tables (regenerated), error catalogue (`error_codes --write`).
- **Tests:** `tests/integration/test_assurance_phase.py` (AC-9 to AC-14).

## Progress log
- 2026-10-24: built; 9 integration tests pass. Two corrections while testing: identifier-only error facts refuse a comma (gates joined with ":"), and a replayed `gate.met` must not open an empty unit of work (MissingAuditEvent), so the derive reads first and suppresses the race. SPEC-314's G6 to G9 providers mean Ready to release, Released and Archived already follow gates (DEC-262).

- 2026-10-24: security review fixes (failing tests first, then code). 0134: actor binding and the forward/one-step check in the SECURITY DEFINER insert trigger `assurance_phase_event_apply`, which also moves the projection; the app role loses UPDATE on `phase`; event `id` insertable so the reason is sealed to it (`reason_of`). New 0135 (down_revision 0134): `assurance.phase_recorded` on the human-only register (0132's 27 + 1; downgrade restores the 27). `derive_phase` walks one step per event; `advance_by_gate` routes SPEC-314's release (G8) and archive lock (G9) through an event; `engagements.api` loses `set_assurance_phase` and `move_assurance_phase`. Stubs authorise before 501; PATCH profile 422s; C5 v1.1 row fields firm-only. Closed lists: schema-check definers and update columns, assurance insert columns. Note: the Brightwater Hale loader still sets `phase` directly as the superuser; A-01-T07 replaces that with service calls.
- 2026-10-26: independent AC tests (A-01-T14): `backend/tests/integration/backfill/test_a01t14_audits_independent.py`; see TASK-1281.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-262 | Phase-to-gate map, order, projection ownership, human-only checks | No |
