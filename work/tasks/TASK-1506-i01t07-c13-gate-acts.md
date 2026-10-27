---
id: TASK-1506
title: I-01-T07 C13 list facts and gate actions (snooze, unsnooze, reassign)
spec: SPEC-308
acceptance_criteria: [AC-1]
risk_zone: red
status: in-review
epic: I-01
branch: s12b-i01t07
created: 2026-10-27
updated: 2026-10-27
---

## Objective
`GET /v1/human-gates` filters (state, band, office, deadline sort) and row facts; snooze, unsnooze and reassign with candidates; the decision card's reassign hook; audit, outbox and the `gate_reassigned` notification (DEC-646).

## Plan (red)
- No migration: 0223 already holds the snooze and reassignment tables, their triggers and the card guard.
- `review/gate_actions.py` (presenter and hook slots, snooze, unsnooze, candidates, reassign), `review/card_reassign.py` (the decision card's hook), `review/gates.py` (filters, `version`), `review/contract.py` (models and four routes), `review/events.py` (`HumanGateReassigned`).
- Matrix: `human_gate.snooze`, `human_gate.reassign` (agent and system denied). Notification kind `gate_reassigned`.
- Tests: I-01-T03's suites lose their strict xfails (the contract file and the DB-backed file).
- Rollback: revert the commit; nothing stored changes shape.

## Open
- Decision cards are not a C13 gate source yet (P-04), so "reassign offers only eligible partners for a reserved card" is held by the hook and 0223's guard but not walked end to end here.

## Progress log
- 2026-10-27: built; lint, pyright and import contracts clean; `make regenerate` run. Tests run in the S12 batch pass.
