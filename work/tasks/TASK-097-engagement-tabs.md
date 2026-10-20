---
id: TASK-097
title: Design foundation, step 4a — the remaining engagement tabs polished (Overview, Review, Map, People, Activity); headings at the plan's sizes, no raw codes on screen, the gaps panel and the activity feed made quiet and readable
spec: SPEC-016
acceptance_criteria: [AC-1]
risk_zone: green
status: done
branch: task-097-engagement-tabs
worktree: spec005
created: 2026-10-20
updated: 2026-10-20
---

## Scope
**In**
- Overview:
  - The three columns align to the top.
  - The area heading and screening counts use the plan's sizes.
  - The audit-area list uses the selected and hover tokens.
- Review: the heading is 15/500, and sources read "a QuickBooks Online export" instead of `import_qbo_gl_csv` (the new `systemName` in `board/join.ts`).
- Map: the gaps pane is a normal pane with a "Needs attention" pill, not an amber block.
- People and Contacts: section headings are 15/500.
- Activity:
  - Times read "Oct 15, 8:08 PM" on one line.
  - The policy chip is mono, and skipped rows are quiet.
  - Actions and reasons the backend emits now have words: `upload_review.start`, `inbox_match.start`, `no_real_model`, `matching_off`, `upload_review_off`, `not_due`.

## Definition of done
- [x] Web tests pass (353); the screens checked on the dev stack.
- [x] `make check-fast` passes.
