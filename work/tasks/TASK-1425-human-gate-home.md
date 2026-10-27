---
id: TASK-1425
title: Migration human_gate_home and the one count source (I-01-T04)
spec: SPEC-313
acceptance_criteria: [AC-1]
risk_zone: red
status: in-review
epic: I-01
plan_key: I-01-T04
branch: s11-home
created: 2026-10-27
updated: 2026-10-27
---

## Objective
The C13 gate half's data for Home: the projection's Home columns, the per-person snooze and
reassignment tables (human-only at the database), the decision card's reassignable column, a
re-projection command, and `GET /v1/human-gates/counts` as the single count source. Acceptance:
up/down/up passes, a rebuild leaves rows unchanged, Daniel's E0 counts read 11 = 3 + 6 + 2 while
Lena Park's omit every Ashford gate.

## Plan
- **Migration `0223_human_gate_home`** (`down_revision = "0220"`; 0221-0222 belong to another
  lane, the batch re-points): `human_gates` + `subkind` (backfilled from `subject_ref->>'type'`,
  then NOT NULL), `office_id`, `blocked`, `blocked_reason_code` (code CHECK, only when blocked),
  `sort_hint`; `kind` admits `evidence_review` (DEC-403); index `(tenant_id, role,
  engagement_id, state)`; `UNIQUE (tenant_id, id)`; insert grant + the new columns, update grant
  + the four derived ones. `human_gate_snoozes` and `human_gate_reassignments`: forced RLS,
  insert-only (revoke, immutable triggers), `actor_kind = 'human'` CHECK, a BEFORE INSERT trigger
  binding `actor_*` to `app.actor_*` and a snooze's `user_id` to that person, FK to the gate in
  the same firm. `decision_cards`: `GRANT UPDATE (reserved_user_id)` plus
  `decision_cards_reassign_guard` (a person, an `awaiting_role` card, status unchanged, a
  reassignment row written in this transaction). SECURITY INVOKER triggers, pinned search path.
- **Projector** (`review/gates.py`): `OpenGate` gains office, blocked, reason, sort hint;
  `plan` reconciles them (`RowValues`); inserts write `subkind`; offices through
  `engagements.api.gate_offices` (work item's, else engagement's).
- **Read**: `_waits_on` (assignee, or unassigned and either no role or a role the caller holds:
  `identity.api.holds_engagement_role`), `_snoozed` (latest row wins), shared by the list and
  `gate_counts`; `GET /v1/human-gates/counts?office_id=` behind `review.grammar_api`
  (`HumanGateCountsOut`); `HumanGateOut` + `subkind`, `office_id`.
- **Command** `python -m abacus_tools.reproject_human_gates <tenant>`.
- **Registries**: review registry, schema_check `IMMUTABLE_TABLES`, `test_schema_check_db`.
- **Tests**: unmark the T04 xfails in `test_c13_gate_half.py` and `test_i01t03_c13_gate_half_ac.py`;
  new `tests/integration/backfill/test_i01t04_human_gate_home.py`; exact lists in
  `test_c13_human_gates.py`, `test_c3_stubs.py`, `test_route_introspection.py`.
- Contract `docs/contracts/home-and-gates.md`; `make generate`. DEC-570.
- Rollback: downgrade 0223 (drops both tables, the guard and the columns; `evidence_review` rows
  deleted first) and revert.

## Progress log
- 2026-10-27: built.
