---
id: TASK-1721
title: Q-04-T011 Independent AC tests for the release windows, gate, flip guard and flip check
spec: SPEC-403
acceptance_criteria: [AC-13]
risk_zone: amber
status: in-review
epic: Q-04
plan_key: Q-04-T011
branch: s14-q04-t011
created: 2026-10-28
updated: 2026-10-28
---

## Objective
ADR-078's independent suite for Q-04-T002 to T004 and T010, written from the P-29 note
(`docs/ops/release-windows.md` §6) with every date typed by hand. Acceptance (backlog row): "The
suite covers Sep 1 00:00 CT, Oct 20 23:59 CT, every deadline week and the Tuesday slot edges, and
fails when any guard is removed."

## Plan
- `backend/tests/unit/tools/test_q04t011_release_windows_independent.py`: window start and end
  edges for all five windows; every weekday of every deadline week refuses promotion (without a
  hotfix) and flips; every in-window Tuesday slot's 18:59/19:00/20:59/21:00 edges and no other
  autumn Tuesday; every mini-freeze day; season Tuesdays but the deadline weeks; the gate's mode,
  rollback, slot and migrate rules; each flip rule alone; the 24-hour journey rule's edges.
- Mutation check by hand: seven guards removed one at a time; each run fails.

## Acceptance
| Check | Test |
|---|---|
| The note's calendar, edges and every guard | the file above (166 tests) |
| Fails when any guard is removed | 7 of 7 hand mutants killed (deadline week in the slot, mini-freeze, rollback, deadline week in the gate, approver, 24-hour journeys, migrate hold) |

## Progress log
- `2026-10-28` — Written; 166 passed. **Finding:** season 2028's deadline week Apr 17–21 ran one
  day past the window's Apr 20 end, so Fri Apr 21 was promotable and flippable. Fixed here
  (`Window.covers`, DEC-810) with the flag calendar following; the whole Q-04 suite (323) passes.

## Handoff
- **Current state:** PR open, held for the batch (stacked on #579).
