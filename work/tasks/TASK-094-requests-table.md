---
id: TASK-094
title: Design foundation, step 3b — the Requests tab is one pane; summary and due date in its header, one line of filters, rows in aligned columns, and adding a request as its last row
spec: SPEC-016
acceptance_criteria: [AC-1]
risk_zone: green
status: done
branch: task-094-requests-table
worktree: spec005
created: 2026-10-19
updated: 2026-10-19
---

## Objective
Replace the stack of tall request cards with a list that scans like a table, keeping everything a reviewer acts on visible.

## Scope
**In**
- `Board.tsx`:
  - The inbox and guidance drafts sit side by side above one Requests pane.
  - Pane header: the title, the summary inline (Requests, Retrieved never asked, Retrievable share, Unclassified), the list's due date, and Import from Excel.
  - The filter bar is one line of compact selects on the band; a 30px column header reads Request, Status, Evidence, Agent screening, Due.
  - Each row shows the request (area, tier), a status pill, the evidence and its flags, the agent's proposal (atom mark, proposal, rationale, citation chips) and the due date. Retrieve, tier and the client-visibility actions sit on a quiet second line.
  - Adding a request is the pane's last row.
- `DueDates.tsx`: the list's due date sits on one line.
- `router.tsx`: Import from Excel moves into the pane header.

**Out**
- A detail drawer. Reviewers act inline today, so the item page keeps the full detail (step 3c).

## Definition of done
- [x] Web tests pass (353); the screen checked on the dev stack.
- [x] `make check-fast` passes.
