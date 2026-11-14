---
id: TASK-7910
title: W-02-T15 WorkbenchSessionWorkflow v2
plan_key: W-02-T15
spec: SPEC-653
acceptance_criteria: [AC-L6, AC-A3, AC-Q1]  # histories replay; read-only turn ends with the code line; out_of_scope outside the pinned scope
risk_zone: red
status: in-review
branch: w02-t15-session-v2
worktree: /Users/ayushkbhatia/Accrued/abacus-s42
created: 2026-11-13
updated: 2026-11-13
---

## Objective
The session workflow's v2 turn behind `workflow.patched("w02-session-v2")`: context layers,
pinned scope, first-message title, edit-and-resend, deterministic compaction, the code's
"Nothing was written.", the plans gate and readiness before each turn.

## Plan (red)
- Files: `workbench/session_turn_v2.py` (new activity), `workbench/session_workflow.py`
  (patched branch), `workbench/api.py` (activity), `workbench/sessions.py` +
  `sessions_contract.py` (`edits_seq`), `agents/session_turns.py` (pinned ports, plans gate,
  `turn_capability_ready`) + `agents/api.py`.
- No migration. Tests: `backend/tests/unit/workbench/test_w02t15_session_v2.py`.
- Rollback: revert; sessions started on v2 keep running (the patch marker stays in their history,
  so a revert needs a deprecate-patch release, ADR-090).
- Security review: at the S42 end pass (red).

## Partial
- ~~Replay histories~~: read-only, child-run (end pass) and side-queue (TASK-7928) recorded; compaction and the plans gate add no workflow command (DEC-4924).
- The FE renders `nothing_written` and `plans_off` notices with W-02-T17's thread states.
- Closed by S43 (2026-11-14, main 322ca3310): W-02-T17 (#1971): WB-01 renders the `nothing_written` and `plans_off` notices.

## Progress log
- 2026-11-13: built; tests written, not run (S42 end pass).
- 2026-11-13 (end pass): v2 histories recorded and replaying; S37's v1 histories still replay.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-4913 | v2 turn activity and its rules | no (ADR-090 versioning) |
| DEC-4914 | readiness before every turn | no |
