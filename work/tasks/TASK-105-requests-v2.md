---
id: TASK-105
title: "Requests v2 (screen): the plan's request words (Requested · Uploaded · Ready for review · Returned · Received), status counts as quick filters, and a request quick-view drawer"
spec: SPEC-022
acceptance_criteria: [AC-5]
risk_zone: green
status: done
branch: task-105-requests-v2
worktree: spec005
created: 2026-10-20
updated: 2026-10-20
---

## Scope
**In**
- One vocabulary for request states: `STATUS.request` in the design system, which `board/join.statusLabel` and `engagementLabels.ITEM_STATUS` now read.
  - open → "Requested"; received → "Uploaded"; ready_for_review → "Ready for review"; needs_revision → "Returned"; accepted → "Received".
  - These are the plan's firm-side words. An upload is never called "received", because the plan uses that word for accepted (domain-model Q-04).
  - The agent's screening proposals keep their own words ("Ready for review", "Needs revision").
- Requests pane:
  - A "Requests by status" row of counts, each a quick filter (on the same URL filter as the selects).
  - A quick-view button beside each request title opens a drawer with details (area, tier, due, client visibility), the evidence, the agent's screening and the request's comments, plus "Open the full page".
- Tests: the status words in `join.test.ts` and `Board.test.tsx`; two new Board tests (counts and filtering, the quick view).

**Out**
- Changing the stored statuses, Draft and Not applicable, and the migration (the plan's F-03-T15, request status v2).
- Bulk actions and linking one request to several procedures.

## Definition of done
- [x] Targeted tests pass; `make check-fast` passes.
