---
id: TASK-6310
title: R-02-T12 governance room backend part 1
spec: SPEC-646  # AC-26 to AC-30; R-02 §3.5
acceptance_criteria: [AC-26, AC-27, AC-28]
risk_zone: amber
status: in-progress
epic: R-02
plan_key: R-02-T12
branch: s32-r02-t12
worktree: /Users/ayushkbhatia/Accrued/abacus-s32
created: 2026-11-09
updated: 2026-11-09
---

## Objective
POR-15's backend: rooms, the `governance_room` scope resolver, letters with per-member state,
the paper without citation markers, and the acknowledgement.

## Plan
- New `assurance/governance_room.py`: `room_scope` (registered with identity), `rooms`, `letters`
  (`roll_up`), `letter` (`paper`), `record_acknowledgement`, `acknowledge`, `LetterChanged`.
- `assurance/api.py` exports; `identity/api.py` exports `display_names`.
- `portal/deliverables_contract.py`: rooms, room communications, letter, acknowledge live.
- Tests: `tests/unit/assurance/test_r02t12_governance_room.py`.
- No migration (0668 and 0710 hold the tables).

## Progress log
- `2026-11-09` — Built; ruff and pyright clean; tests written, not run (end pass). Partial:
  recipients to `tcwg` grants and invitations are issued at send time by A-07-T26's send path
  (this row reads the grants); the letter PDF route and the C10 governance-letter deliverable,
  inquiries, reports and private questions still answer 501 (R-02-T21 and the send path); the
  `portal.governance_room` flag arrives with R-02-T14.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-3010 | Room = body; tcwg grant plus current membership opens it; per-reader states; sealed sections format; idempotent acknowledgement | no |
- `2026-11-09` — S32 end pass: gates, unit, contract, S32 integration and web suites run; fixes folded into the end-pass PR. Status partial.
- `2026-11-09` — Partials round (branch s32p-a07-t26-grants, DEC-3026): approve & send issues
  each recipient's `tcwg` grant on the room, or a pending grant and invitation; unit tests in
  `tests/unit/identity/test_a07t26_tcwg_grant.py`.
