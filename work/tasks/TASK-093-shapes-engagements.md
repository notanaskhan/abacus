---
id: TASK-093
title: Design foundation, step 3a — controls are squared rectangles, not pills; the engagements index is one searchable pane; setup steps and independence confirmations are compact
spec: SPEC-016
acceptance_criteria: [AC-1]
risk_zone: green
status: done
branch: task-093-shapes-engagements
worktree: spec005
created: 2026-10-19
updated: 2026-10-19
---

## Objective
The founder asked for squared shapes in place of pills (2026-10-19). Step 3a also starts the page rebuilds with the engagements index (the plan's T1).

## Scope
**In**
- Shapes:
  - Buttons, tabs, toolbar chips, the bell, the dialog close and the rail buttons use 7px corners; status badges and citation chips use 5px.
  - Dots, avatars and progress tracks stay round.
  - This deviates from the plan's 999px pill radius, at the founder's request.
- Engagements index: one pane containing:
  - the title and count;
  - an Active / Archived / All segmented filter with counts;
  - a search over engagement, client and entity;
  - New engagement;
  - a 40px-row table (engagement, client, type, period, status pill) where clicking a row opens the engagement;
  - "Nothing matches" when the filter or search hides every row.
- Setup steps become a four-column grid; done steps are quiet and drop their detail.
- Independence confirmations show three, then "Show all n". Each row is one line with the actions on the right.
- Engagements test: the status reads "Active" (a pill, not the raw value), scoped to the table.

## Plan
Approved by founder (2026-10-19). Path: `packages/ui/src/**`. Approval file: `work/approvals/TASK-093.yaml`.

## Definition of done
- [x] Web tests pass (353); the screen checked on the dev stack.
- [x] `make check-fast` passes.
