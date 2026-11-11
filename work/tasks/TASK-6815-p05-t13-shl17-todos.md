---
id: TASK-6815
title: "P-05-T13: SHL-17 To-do drawer and My to-dos on C-30 ToDoRow, ToDoGroup and DueChip; Undo through reopen"
spec: SPEC-650
acceptance_criteria: [AC-17, AC-21, AC-23, AC-24, AC-25]
risk_zone: green
status: in-review
branch: s36-p05-t13
worktree: /Users/ayushkbhatia/Accrued/abacus-s36
created: 2026-11-11
updated: 2026-11-11
plan_key: P-05-T13
---

## Objective
SHL-17 a–f render from data, Create to-do stays disabled until title and assignee are set, and the
Undo toast calls only POST /v1/todos/{id}/reopen.

## Built
- C-30 in `apps/web/src/domain/collaboration/todos.tsx`: `DueChip` (derived words: "Wed Sep 16 · 2
  days", "Today", "Overdue · Sep 18", "Due Sep 28"; compact "Sep 16" in lists), `Ring`, `ToDoRow`
  (from-initials and linked chip, unread dot), `ToDoGroup` (band with count, red-tint overdue).
- `apps/web/src/screens/SHL-17/` (`index.tsx`, `copy.ts`, `scenarios.ts`, test) and
  `fixtures/scenarios/SHL-17.ts`: a–f from the P-05-T03 seed; New to-do with the Northwind team
  picker (never the agent) and Create disabled until title and assignee; Mark done → host complete
  and the "To-do done · Undo" toast whose Undo calls only the host's reopen; Reopen on done.
- `docs/screens/SHL-17.md` states move to fixture.

## Progress log
- `2026-11-11` — Built (S36). Tests written, not run (end pass).

## Partials
- `?ov=todos` deep link and AUD-09's "··· Add to-do…" menu and chips are not wired: AUD-09 carries
  locked parity frames, so its wiring lands with its next row (the drawer takes the anchor).
- Checklist toggles and "Draft request…" are display-only here; the live writes come with the
  route wiring.
