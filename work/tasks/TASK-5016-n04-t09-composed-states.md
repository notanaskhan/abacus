---
id: TASK-5016
title: N-04-T09 remainder - NOT-01's composed states, assignee picker, corrections saved at Create
spec: SPEC-000  # row
acceptance_criteria: [AC-1, AC-2, AC-3]
risk_zone: green
status: in-review
epic: N-04
plan_key: N-04-T09
branch: s26r-n04-t09-states
worktree: /Users/ayushkbhatia/Accrued/abacus-s26
created: 2026-11-06
updated: 2026-11-06
---

# TASK-5016 · N-04-T09: NOT-01's composed states

TASK-3232 drew b, c and d and left the composed states out.

AC-1: a possible duplicate shows "Looks like N2 · same notice" with Attach and Create anyway, and
takes Create notice away.

AC-2: manual entry names its reason, offers empty fields and shows no confidence pills.

AC-3: no client matched shows the picker, and Create notice stays off until a person picks one.

## Decisions (DEC-2329)
- A person's typed corrections were never sent: only Confirm saved anything, so Create notice dropped
  every edit. They now save first, which manual entry depends on.
- The client list has no entities, so with no candidates the picker takes a client, then its entity.
- Assignee is a picker over the firm's members, defaulting to the person.
- Draft Form 2848… stays disabled and says why: T-01's request route is a stub until the firm's form
  templates are loaded on P-11's renderer. That template is firm content, not code.

## Known limits
- Create anyway takes no reason yet (N-04 US-2.3 asks for one); the contract has no field for it.
- The client picker lists the first 100 clients.
- Page thumbnails in manual entry are not drawn: the viewer owns them.

## Progress log
- 2026-11-06: built on main 49922a2fd; 16 NOT-01 tests pass, tsc and eslint clean.
