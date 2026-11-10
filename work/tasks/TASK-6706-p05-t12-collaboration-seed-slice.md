---
id: TASK-6706
title: "P-05-T12: Brightwater Hale seed slices and fixture export: Northwind comment and to-do, Marcus's four open to-dos, the 23-event Northwind timeline"
spec: SPEC-650
acceptance_criteria: [AC-1, AC-7, AC-17, AC-31]
risk_zone: green
status: in-review
branch: s35-p05-t12
worktree: /Users/ayushkbhatia/Accrued/abacus-s35
created: 2026-11-10
updated: 2026-11-10
plan_key: P-05-T12
---

## Objective
make seed-demo and fixture mode show identical SHL-17, SHL-18 and AUD-29 data, and the golden counts 4 = 1+1+2 and 23 = 12+11+0 pass.

## Plan
1. `brightwater_hale/collaboration_slice.py` (new, `--slice collaboration`, needs `audit_core`):
   SHL-18a's comment (MO, 12:35 PM, Exceptions!A3, mentioning HL) and four to-dos (SHL-17a's row 6
   to-do with its checklist; Marcus's 1 overdue + 1 today + 2 this week).
2. Loader handlers `collaboration.thread_seeded` and `collaboration.todo_seeded` call
   `collaboration.api.open_thread` / `create_todo` as the person (never direct inserts), on
   Northwind's Internal Control paper (found or created as the completion slice does).
   `collaboration.api` now exports both services.
3. Test: `tests/unit/synthetic/test_p05t12_collaboration_slice.py` (handlers, needs, 4 = 1+1+2,
   every title, due date and checklist item equal to the fixture seed).

## Partial
- **The 23-event timeline.** AUD-29 shows no collaboration events except deletions and
  redactions, so Northwind's 23 events by 2:30 PM are the other slices' audit events. Their count on
  a full `make seed-demo` (12 Human + 11 via Agent + 0 Policy) is checked on a seed-demo run with
  Docker, not in this session; the AC suite seeds its own 23 (P-05-T08).
- Fixture ids for the to-dos are stable ids; the seeded ones are the service's. The data (titles,
  people, dates, checklists, anchors) is identical, the ids are not.
- `collaboration.v2` is not turned on by the seed (ADR-236 not accepted; DEC-3200).

## Progress log
- `2026-11-10` — Built; tests written, not run (end pass).
