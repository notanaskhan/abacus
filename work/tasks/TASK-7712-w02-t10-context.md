---
id: TASK-7712
title: W-02-T10 Context options and context items with code summaries
plan_key: W-02-T10
spec: SPEC-653
acceptance_criteria: [AC-C3, AC-C4, AC-C5]
risk_zone: amber
status: in-review
branch: w02-t10-context
worktree: /Users/ayushkbhatia/Accrued/abacus-s41
created: 2026-11-13
updated: 2026-11-13
---

## Objective
WB-02's picker over records the viewer can open, attaching and removing context with
code-computed summaries and an honest `client_scope`.

## Plan (amber)
- Files: `workbench/session_context.py` (new), `workbench/list_contract.py` (three routes
  answer), `engagements/work_item_facts.py` + `engagements/api.py` (`work_item_ids_of`,
  `engagements_for` exported).
- No migration (0850 widened the item kinds); matrix rows exist.
- Tests: `backend/tests/unit/workbench/test_w02t10_session_context.py`.
- Rollback: revert; the routes answer 501.

## Partial
- S41 gaps (DEC-4734): the workpapers card now carries the decided materiality and version when
  the viewer may read it. S41 leftovers (TASK-7733, DEC-4738): AC-C4's lines are built: the client record line
  (plan number, plan year, participants with balances at BOY, behind `ebp.read`) and the workpaper
  line ("Trial Balance · Prepared · MD · Materiality v2 · $252,200 · Internal Control · 7
  exceptions", each part behind its read). Still open: the PBC line's "3 files in use", which no
  spec, contract or table defines.
- The picker offers the three kinds the spec's three tabs need (`client_record`, `documents`,
  `workpapers`); a client without an engagement and single documents are not in SPEC-653 or the
  epic (not a gap; S41 leftovers scan).

## Progress log
- 2026-11-13: built; OpenAPI export clean; tests written, not run.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-4715 | options, attach/remove and summaries | no |
