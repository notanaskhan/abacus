---
id: TASK-7711
title: W-02-T09 Session list and CRUD with DEC-87 visibility, counts and search
plan_key: W-02-T09
spec: SPEC-653
acceptance_criteria: [AC-L1, AC-L2, AC-L3, AC-L4, AC-L5, AC-V1, AC-V2, AC-V3]
risk_zone: amber
status: in-review
branch: w02-t09-session-list
worktree: /Users/ayushkbhatia/Accrued/abacus-s41
created: 2026-11-13
updated: 2026-11-13
---

## Objective
WB-01's list under DEC-87 with filters, counts and title search, the blank create, the owner's
rename and soft delete.

## Plan (amber)
- Files: `workbench/session_list.py` (new), `workbench/sessions_contract.py` (list and blank
  create answer; `summary_of`), `workbench/list_contract.py` (rename and delete answer).
- No migration (0850's columns); matrix rows exist (W-02-T03).
- Tests: `backend/tests/unit/workbench/test_w02t09_session_list.py`.
- Rollback: revert; the routes answer 501 again.

## Partial
- C15: no workbench session search projection (palette search for sessions); list topics on
  `/v1/events` (TanStack invalidation): the SSE badge stream (P-10) covers running counts.
- `agent_label` for via-Agent rows waits for agent definitions' names (W-03).
- Membership by engagement team uses the viewer's engagement roles; DEC-4601's "initiated"
  (runs the viewer started inside another's session) is not separately queried.

## Progress log
- 2026-11-13: built; OpenAPI export clean; tests written, not run.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-4714 | list membership, filters, rename version and soft delete | no |
