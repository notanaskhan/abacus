---
id: TASK-366
title: Engagement transitions and gates — the lifecycle table, 409 illegal_transition, human-only accept/decline/hold, per-type gate policy in require_open (F-03-T13)
spec: SPEC-025
acceptance_criteria: [AC-7]
risk_zone: amber
status: done
epic: F-03
plan_key: F-03-T13
branch: f03-t13-transitions
created: 2026-10-22
updated: 2026-10-22
---

## Objective
"Every illegal transition answers 409, accept/decline/hold refuse agent and system principals, and
a non-attest close engagement opens client data on G1+G3 without G2."

## Plan (amber)
- `engagements/transitions.py`: `LIFECYCLE`, the chapter 03 §3.1.3 table as data (eight states,
  eight moves, each `human` with its matrix action or `system`); `move_for` raises
  `IllegalTransition` (409 `illegal_transition`, facts `from_status`, `to_status`);
  `transition(tx, engagement_id, to, by=…)` refuses a human move to any principal that is not a
  signed-in person (`Forbidden` before anything is written) and checks the matrix, refuses a system
  move to a person, requires a hold reason code, and writes one audit event (`engagement.accepted`,
  `.held` …) and one `engagement.status_changed` outbox event in the caller's unit of work;
  `hold` and `resume`.
- Matrix: `engagement.hold` (engagement partner and manager, fresh MFA; agents and the system
  denied by omission).
- `setup.record_acceptance`: a `prospect` engagement's first decision moves it to `accepted` or
  `declined` through `transition`.
- `setup.require_open` and the setup view: the gates that apply come from the type's gate policy
  (`required_gates`), so tax and non-attest CAS open on G1 and G3 without G2, and a notice on G3.
  Each blocker carries its gate as a fact (`{"gate": "G1"}`).
- No migration (the 8-state CHECK is 0069). Rollback: revert the commit.

## Decisions
- The blockers keep their codes (`acceptance_missing`, `independence_conclusion_missing`,
  `letter_missing`, `acceptance_declined`), which the web app already maps to copy, and add the
  gate as a fact; chapter 03's `gate_unmet` name is for gates beyond G1 to G3 as their owners land.
- Engagements created before this (status `active`) are not moved back to `prospect`; the
  transition applies to engagements created in `prospect`.

## Definition of done
- [x] `tests/unit/engagements/test_transitions.py` (every illegal pair of the 64, human-only
  refusals for agents and the system, the per-type opening)
- [x] Backend unit and acceptance suites (14,540 passed); engagement, backfill and security
  integration tests (650 passed; one assertion now expects the gate fact)
- [x] `make check-fast`

## Progress log
- 2026-10-22: `tests/unit/engagements/test_gates.py` passed only after another test had imported
  the engagements api (which registers G1 to G3); it now imports it itself.
