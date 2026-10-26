---
id: TASK-1304
title: C13 gate half - red-zone service ticket and ADR-078 AC suite (I-01-T03)
spec: I-01 §3 (F1, F6, F8), §4.2, §4.3
acceptance_criteria: [I-01-T03]
risk_zone: red
status: in-review
epic: I-01
plan_key: I-01-T03
branch: s10-i01-home
created: 2026-10-26
updated: 2026-10-26
---

## Objective
The service ticket for N's red C13 gate half (I-01-T04 migration and counts, I-01-T07 list facts,
snooze and reassign) and its independent acceptance suite, committed before T04 opens and
failing against the stub.

## Service ticket (for I-01-T04 and T07, `review`, red)
- Migration `human_gate_home`: `human_gates` gains `subkind`, `office_id`, `blocked`,
  `blocked_reason_code`, `sort_hint`; insert-only `human_gate_snoozes` (latest per gate and user
  wins) and `human_gate_reassignments` (`actor_kind = 'human'` bound to the transaction GUCs);
  `decision_cards` column grant on `reserved_user_id`; re-projection command.
- `GET /v1/human-gates/counts?office_id=` → `{total, bands {decisions, sign_offs, agent_outputs,
  approvals_sends}, overdue, snoozed}`: open, assigned to the viewer (or by role when unassigned),
  not snoozed by them, walls excluded with nothing counting what was left out.
- `GET /v1/human-gates` gains `state`, `band`, `office_id`, `sort=deadline` and per-row
  presentation facts from `resolve_many` (subkind, band, title, context, blocked, bulk_eligible,
  subject_route, overlay, glyph, allowed_actions, version, proposed_by).
- `POST …/snooze {until}` · `/unsnooze` (`human_gate.snooze`, assignee only; 422
  `snooze_past_due`, `snooze_in_past`; 409 `gate_not_open`, `gate_overdue`);
  `GET …/reassign-candidates`, `POST …/reassign {to_user_id, seen_version}`
  (`human_gate.reassign`; 409 `not_reassignable`, `stale_version`; 422 `candidate_not_eligible`),
  through the owner's hook in its unit of work; audit and outbox `human_gate.snoozed`,
  `.unsnoozed`, `.reassigned`; notification `gate_reassigned`.
- Agent, system and support refused at the matrix for snooze and reassign; shadow-stage
  proposal gates suppressed (I-01-T08).

## Suite
- `tests/contracts/c13_home/test_c13_gate_half.py`: matrix and wire (routes, actions, params,
  shapes, error codes, tables and the human-only CHECK).
- `tests/integration/backfill/test_i01t03_c13_gate_half_ac.py`: against P-04's projection and its
  P-04-T17 harness: one count source by band, walls on counts, office as a filter, snooze on
  every surface and its bounds, reassign through the hook, presentation facts and attribution.
- What holds on main passes now (no agent, system or client reader; the list's counts per kind;
  walls on the list). Everything T04 and T07 add is `xfail(strict=True)` citing TASK-1304
  (DEC-399), so the suite fails against the stub and passes unedited once they land.
- Placement: the plan names `backend/tests/ac/`; the repo has no such folder and keeps ADR-078
  suites beside their harness, so the DB-backed half lives in `tests/integration/backfill/`.
- Gap: shadow-stage suppression has no gate-side key until I-01-T08 maps agent stages to gates;
  it stays in T08's own acceptance and is not asserted here.

## Progress log
- 2026-10-26: ticket and suite written (no product code).
