---
id: TASK-096
title: Design foundation, step 3d — Fieldwork as a cockpit; a sticky procedures rail with each one's state, and a canvas of sections (materiality, journal entry testing, the search for unrecorded liabilities) with its setup grouped
spec: SPEC-037
acceptance_criteria: [AC-1]
risk_zone: green
status: done
branch: task-096-fieldwork-cockpit
worktree: spec005
created: 2026-10-19
updated: 2026-10-19
---

## Objective
Give fieldwork the plan's record-cockpit shape (T2) instead of a column of cards.

## Scope
**In**
- `Fieldwork.tsx`:
  - A sticky "Procedures" rail with three rows (materiality, journal entry testing, the search for unrecorded liabilities). Each row shows a one-line summary and its state ("To set / Set", "Not started", "Set up", "Selecting", "n selected", "Needs attention"), and jumps to its section.
  - Each section has a 15/500 heading with the state pill.
  - The search's setup groups the subsequent-period ledger and timing bands side by side, with the accounts below.
  - Inner panes are titled "Selection" and "Not started", so a section doesn't repeat its heading.

**Out**
- Sample approval, L1/L2 sign-off on each row, and the plan → sample → request → test flow. Those are behaviour changes for their own task.

## Definition of done
- [x] Web tests pass (353); the screen checked on the dev stack.
- [x] `make check-fast` passes.
