---
id: TASK-6400
title: N-04-T06 remainder - masked TIN, return label, due date and alerts follow the respond-by, search, retention types
spec: SPEC-000  # row
acceptance_criteria: [AC-1, AC-2, AC-3]
risk_zone: amber
status: in-review
epic: N-04
plan_key: N-04-T06
branch: s26p-n04-t06-detail
worktree: /Users/ayushkbhatia/Accrued/abacus-s26
created: 2026-11-08
updated: 2026-11-08
---

# TASK-6400 · N-04-T06: notice detail, due date and alerts follow the respond-by, search, retention

TASK-3210 left the notice detail's masked TIN and return label empty, the work item's due date and the response alerts untouched by a corrected respond-by, and no search document or retention record type.

AC-1: The notice detail carries the taxpayer's masked TIN (the entity's kind, the adopted last four) and the related return's label.

AC-2: A corrected respond-by moves the work item's due date in the same unit of work and signals the response workflow's `respond_by_changed`.

AC-3: The notice has a C15 search document with no amount, and `notice` and `notice_response` are retention record types.

## Decisions (DEC-2950)
- The work item's due date is moved through a new `engagements.api.set_work_item_due(tx, …)` in the notice's own unit of work, like `archive_work_item`.
- `notice_response` was already the letter's retention type (N-04-T16) but not one evidence knew, so a retention lookup for it would have raised. Both types are added; their years are content (QN-7).
- The response workflow had a `respond_by_changed` signal nobody sent; it is sent after the correction commits.

## Known limits
- The retention floors and defaults for `notice` and `notice_response` are content (counsel, QN-7) and are not loaded here.
- `search_document` has no indexer calling it on main yet; the projection is registered like tax's.

## Progress log
- 2026-11-08: built on main a801fff01; tests written, run at the S26 partials end pass.
