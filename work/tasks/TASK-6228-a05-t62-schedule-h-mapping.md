---
id: TASK-6228
title: A-05-T62 close, the Schedule H line mapping publishes through an endpoint
spec: SPEC-640
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
epic: A-05
plan_key: A-05-T62
branch: s31c-a05-t62
worktree: /Users/ayushkbhatia/Accrued/abacus-s31
created: 2026-11-08
updated: 2026-11-08
---

## Plan (amber)
- `assurance/schedule_h_mappings.py`: `POST /v1/ebp/schedule-h-mappings:publish` (dry run first; publishing needs a person and fresh MFA).
- Matrix action `ebp_schedule_h_mapping.publish` (quality partner, practice leader).
- Audit action `ebp_schedule_h_mapping.published`.
- No migration (0665's table is insert-only and published on insert).
- The runbook's gap is closed, and the contract doc is updated.
- Test: `test_a05t62_schedule_h_mappings.py`.
- Rollback: remove the route and the matrix row (a published version stays, as all content does).

## Progress log
- 2026-11-08: built; runs at the close end pass.
