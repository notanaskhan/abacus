---
id: TASK-1190
title: Human-gate projector, gate sources, GET /v1/human-gates (P-04-T16)
spec: SPEC-313
acceptance_criteria: [AC-1]
risk_zone: red
status: done
epic: P-04
plan_key: P-04-T16
branch: s8a-evidence-pipeline
created: 2026-10-25
updated: 2026-10-25
---

## Objective
No SPEC covers the C13 projection; the acceptance source is P-04 §3 F9 (the epic), so `spec` names the review grammar's nearest spec for the docs gate. The main session may retarget it when a C13 spec exists.

"Replaying the same events leaves human_gates unchanged, walled clients never appear, and one query yields Daniel Reyes's 11 = 3 + 6 + 2." This row builds the projector, the source slot and the read; the 3 + 6 + 2 needs decision cards, sign-off requests and exports as sources, which register in their own rows (I-01, P-04 services).

## Plan (red zone)
- **Slot:** `review/gates.py` `register_gate_source(GateSource)`: an owner names its gate kind, subject type, the read action that admits a person to its gates (`visible()`), the outbox events that may change it and `open_for(tenant, engagement_id | None)` (what waits on a person now). `register_gate_kind` (P-04-T06) stays the computed-gate check slot (DEC-320).
- **Projector:** `HumanGateProjector` = `review.api.SUBSCRIPTIONS` on a fixed C13 event set. For an event it reconciles the engagement's rows of each subscribed source with `open_for`: a new subject is inserted `open` (its `source_event_id` derived from the event and subject, so a redelivery inserts nothing), a closed one goes `done`, a reopened one `open`; unchanged rows are not written. `rebuild_human_gates(tenant)` reconciles every engagement. System unit of work, audited `human_gate.projected` on the engagement only when a row changed.
- **Sources (agents):** `screening_result` (latest per version, no live review decision, version not withdrawn), `upload_review` (latest per version with a shown flag, same), `inbox_match` (latest run per waiting inbox file with a shown proposal), `guidance_draft` (latest per item, passed checks, undecided) as `proposal` gates (DEC-28).
- **Events (new, identifiers only):** agents `proposal.recorded {engagement_id, source}` (four writers), `guidance_draft.decided`; evidence `review_decision.recorded` (decide and undo), `inbox_file.sorted` (assign and discard); plus the existing `evidence_version.withdrawn`.
- **Read:** `GET /v1/human-gates` served behind `review.grammar_api`: open rows assigned to the caller or unassigned, through `visible(human_gate.read)` and the source's read action (walls answer nothing), keyset by `(created order, id)`, `counts` per kind.
- **Migration 0152** (`projection_keys`, down 0146): unique `human_gates (tenant_id, kind, subject_ref)`. Rollback: `alembic downgrade 0146`.
- **Closed lists:** worker pinned subscriptions (review joins MODULES; four new event types), C13 notes in the README.
- **Tests:** `tests/unit/review/test_human_gate_plan.py` (reconcile pure logic, slot refusals), `tests/integration/backfill/test_p04t16_human_gate_projector.py` (it shares the back-fill fixtures) (AC: replay unchanged, rebuild equals, walled client absent, four sources project as `proposal`).

## Progress log
- 2026-10-25: built as planned. The C13 events didn't exist: added `proposal.recorded` (four agent writers), `guidance_draft.decided`, `review_decision.recorded` (decide and undo) and `inbox_file.sorted` (assign and discard). Agents read no evidence table, so `evidence.api.decided_among` and `waiting_among` answer for the sources. A reconcile reads the owner after taking a transaction advisory lock, so two events about one engagement never interleave. 10 unit and 5 integration tests pass. **Deferred:** decision, sign-off-request, send and export sources (their owners' rows; I-01); the `review.rebuild_human_gates` operator command wrapper (the function is `review.api.rebuild_human_gates`); P-04-T17's independent suite.
- 2026-10-25 (close): full `tests/unit tests/contracts tests/security` 28,473 passed (2 C3/C5 stub tests updated to mark the served routes live, the repo's `LIVE` pattern); integration, workflow and hostile-file run 996 passed + `test_schema_check_db` 192 passed after pinning `inbox_files.sort_outcome`; `make check-fast` green.
- 2026-10-26: P-04-T17's independent suite: `backend/tests/contracts/review_grammar/test_c13_human_gates.py` and `backend/tests/integration/backfill/test_p04t17_human_gates_independent.py` (TASK-1279); no defect.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-320 | `register_gate_kind` already means computed gate checks; the projection slot is `register_gate_source` | No |
