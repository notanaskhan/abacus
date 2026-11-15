---
id: TASK-8069
title: "T-07-T03 part: the interpretation's L3 gate and the reading's notifications"
spec: SPEC-656
acceptance_criteria: [AC-4]
risk_zone: amber
status: in-review
branch: t07-t03-reader-gates
worktree: /Users/ayushkbhatia/Accrued/abacus-s45
created: 2026-11-15
updated: 2026-11-15
plan_key: T-07-T03
---

## Objective
The part of T-07-T03 that S45's T12 instrument service and T13 reader unblocked. It adds the C13
kind `instrument_interpretation_approval` and the C16 kinds `instrument_interpretation_ready` and
`instrument_read_finished` (T-07 §4.8; SPEC-656 AC-4.1).

## Built
- `tax/instrument_events.py`: four events, carrying identifiers and codes only.
  - `instrument_interpretation.adopted`: emitted once, when a person's write first moves the
    interpretation into Adopted.
  - `.approved`: emitted by the L3 lock.
  - `.reopened`: emitted by a reopen.
  - `instrument_read.finished`: emitted from the reader activity, with its outcome and code.
- `tax/instrument_gates.py`: the HOME-02 `sign_off_request` row.
  - It is raised for each current interpretation at Adopted, with role `manager`.
  - Read action: `instrument.read`.
  - The row links to `TXT-01?returnId=…&ov=signoff`.
- C16 catalogue:
  - `instrument_interpretation_ready`: to the engagement's managers (new
    `identity.api.engagement_managers`), never the adopter.
  - `instrument_read_finished`: to the run's initiator. It is agent-originated, so it offers no
    inline action.
  - Both are written to `docs/contracts/notifications.md`.
- Tests:
  - `tests/unit/tax/test_t07t03_reader_gates.py`.
  - C13's fixed event set now includes the three interpretation events.

## Partial
`fiduciary_computation_sign_off` (T16) and `estate_values_approval` (T22) register with their
services.

## Progress log
- `2026-11-15` — Built (DEC-5056). Lint and type-check clean; the tests run at the end pass.
