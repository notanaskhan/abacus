---
id: TASK-102
title: "Home: \"Waiting on you\" — samples to approve, rows to sign or review, evidence to decide and overdue client items across the person's engagements, approvals first"
spec: SPEC-040
acceptance_criteria: [AC-11]
risk_zone: red
status: done
branch: task-102-home-queue
worktree: spec005
created: 2026-10-20
updated: 2026-10-20
---

## Objective
Give each person one place that says what's waiting on them (the plan's HOME-01/02, epic I-01), built on the TASK-101 DataTable.

## Scope
**In**
- `identity.my_engagements(ctx)`: the caller's own firm roles by engagement (own rows; LIST_EXEMPT).
- Three `OWN` routes; each module answers for its own work, and the screen joins them:
  - `GET /v1/firm/waiting/fieldwork` (fieldwork `flow.waiting_for`): samples to approve (partner or manager), tested rows to sign as preparer (staff, senior, manager) and rows someone else prepared to review (senior, manager, partner). Read through `visible()`.
  - `GET /v1/firm/waiting/review` (evidence `review_waiting`): versions waiting for a decision per engagement where the caller decides (partner, manager, senior). Counted without building the queue's entries, eight engagements at a time; engagements the caller can't read are skipped.
  - `GET /v1/firm/waiting/overdue` (requests `overdue_mine`): open or sent-back client items past due, in one grouped query through `visible()`.
- Web:
  - `home/queue.ts` (pure join): ranked approve → review/decide → sign → follow up, worded in the singular or plural.
  - `home/WaitingOnYou.tsx`: a DataTable with To do, Engagement and an action button; a row opens the tab where the work is done. Lists show as they arrive.
  - Mounted above the independence confirmations on the engagements page.

**Out**
- One batched query for decisions waiting. It needs request fulfilments across engagements; today it's about 5 seconds for 52 engagements on a loaded dev box.
- A dedicated "Home" nav item and route.

## Definition of done
- [x] `queue.test.ts` (2); the engagements and independence screen tests pass; `make check-fast` passes.
- [x] Checked live: Sam sees "Decide 1 piece of evidence", "Sign 1 tested row of journal entry testing as preparer" (after he changed a signed result) and "10 client items are past due".
- [ ] Owed: ADR-078 integration tests for the three routes.
