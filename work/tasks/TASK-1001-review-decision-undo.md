---
id: TASK-1001
title: Evidence decision Undo — migration 0117, effective-decision reads, undo route, review_decision.undone (P-01-T13)
spec: SPEC-004
acceptance_criteria: [AC-11, AC-12]  # amended by P-01 AC 3.1.4 and 3.1.4b (Undo, then decide again)
risk_zone: red
status: in-progress
epic: P-01
plan_key: P-01-T13
branch: s6-review-integrity
created: 2026-10-24
updated: 2026-10-24
---

## Objective
"Undo within 10 s restores Uploaded - needs review, the same version can then be decided again, and after 10 s Undo returns 409 undo_window_closed." (P-01-T13; DEC-24; ADR-161 clause 6.)

## Plan (red zone)
- **Migration `0117_review_decision_undo.py`** (down_revision `0116`, the head on origin/main after the rebase; the main session re-chains if needed):
  1. `decision` CHECK widened with `undone`;
  2. `decision_seq smallint NOT NULL DEFAULT 1`; `review_decisions_once` replaced by `review_decisions_seq_once UNIQUE (tenant_id, evidence_version_id, decision_seq)` and `review_decisions_undo_parity CHECK ((decision = 'undone') = (decision_seq % 2 = 0))`;
  3. `review_decisions_reason` rewritten as `(decision IN ('accept','undone')) = (reason_code IS NULL)`;
  4. `undoes_decision_id uuid NULL`, `CHECK ((decision = 'undone') = (undoes_decision_id IS NOT NULL))`, FK `(tenant_id, undoes_decision_id)`, `review_decisions_undone_once UNIQUE (tenant_id, undoes_decision_id)`; an undone row carries no note, screening result or correction;
  5. the SECURITY DEFINER `review_decision_reason_check()` (same name, already in `schema_check`) also requires `decision_seq` = the version's max + 1, and an `undone` row to undo the row at `decision_seq - 1`, of the same version and item, by the same actor, within 10 s of business time (`abacus_now()`), else `undo_window_closed`;
  6. `insert_columns` gains the two columns;
  7. `abacus_human_only_actions()` redefined with `review_decision.created` and `review_decision.undone` (the YAML listed `review.decided`, a log line, so the real audit action was unguarded; verb `decide`).
  Downgrade refuses while any row has `decision_seq > 1`. Rollback: `alembic downgrade 0116`.
- **Service (`evidence/service.py`):** effective decision = the version's highest-numbered row when odd. `_reviewable` and the `_ONE_DECISION` mapping use it (`review_decisions_seq_once`, `review_decisions_undo_parity` → `already_decided`); `decide` writes the next `decision_seq`. New `undo_decision(ctx, engagement_id, decision_id)` (route) and `undo_review_decision(tx, ctx, engagement_id, decision_id)` (in the caller's unit of work, for P-04-T29) — live human only, not support; `review_decision.undo` authorised, then the original's own action; same actor; only the effective decision; 10 s on `kernel.clock.now`; items back to `uploaded` through `requests.api.reopen_after_undo`; audit `review_decision.undone`; outbox `request_item.status_changed`.
- **Repository:** `effective_decision`, `decision_by_id`, `next_decision_seq`; `list_review_state`, `item_versions_with_decisions`, `decisions_for_screenings` read effective decisions only. `abacus_tools/agent_stage.py` skips undone rows.
- **Contract first:** `POST /v1/engagements/{engagement_id}/review-decisions/{decision_id}/undo` → `UndoneDecisionOut` (201); matrix row `review_decision.undo` in `evidence.yaml` (the same cells as `evidence.accept`/`reject`, agent and system deny) — one action per route, and the service also authorises the original decision's action (DEC-214); `make regenerate`.
- **Errors:** `UndoWindowClosed` (`undo_window_closed`, 409) in evidence; `error_codes --write`.
- **Registry:** `INSERT_COLUMNS["review_decisions"]` gains `decision_seq`, `undoes_decision_id`.
- **Tests:** `tests/integration/test_review_decision_undo.py`: AC 3.1.4 (undo restores `uploaded`, original untouched, audit names the person), AC 3.1.4b (re-decide, second undo 409, DB refuses a second effective decision and a second undo), window after 10 s (service and trigger), another person 403, agent/system refused, migration constraints; `test_human_only_guard.py` covers the two new actions by parametrisation.

## Progress log
- 2026-10-24: plan written; building.
- 2026-10-24: built as planned. `tests/integration/test_review_decision_undo.py` 8 pass (AC 3.1.4 undo restores `uploaded` with the original untouched and the audit naming the person; 409 after 10 s; 403 for another person; send-back undone; AC 3.1.4b re-decide by another reviewer and a second Undo 409; 409 `already_decided` for a second decision; agent and worker refused; the 0117 trigger and CHECKs). Related: human-only guard (with the two new actions), J02 journey, generated matrix and route introspection, agent principal, evidence unit tests: 3820 passed. P-01-T15 registers the route in P-04-T13's conformance suite (not built yet).
- 2026-10-24: security review fixes: a decision records the version's assignee and each item's prior status (0117 columns `prior_assignee_user_id`, `prior_item_statuses`) and Undo restores both, so undoing a send-back of an already Returned item leaves it Returned (DEC-214 updated). Tests written failing first in `test_review_decision_undo.py`.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-214 | One action per route vs "the same action as the original decision"; where Undo puts the item; the outbox event; the human-only register gap | No (ADR-161) |
