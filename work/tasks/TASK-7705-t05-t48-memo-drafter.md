---
id: TASK-7705
title: T-05-T48 tax.memo_drafter capability
plan_key: T-05-T48
spec: SPEC-651
acceptance_criteria: [AC-F9]  # memo drafted by reference, verified, never signed by the agent
risk_zone: red
status: in-review
branch: t05-t48-memo-drafter
worktree: /Users/ayushkbhatia/Accrued/abacus-s41
created: 2026-11-13
updated: 2026-11-13
---

## Objective
The preparer memo drafter: a model drafts prose from code-computed figures and citation handles;
code settles every number and citation, keeps human-owned sections and regenerates only affected
ones; the version is stored as the agent's draft.

## Plan (red)
- Files: `tax/memo_drafter.py` (models, `settle`, hashes, `draft_memo`),
  `agents/specs/v2/tax.memo_drafter.yaml` + regenerated `_specs_v2.py`,
  `ai_gateway/prompts/tax.preparer_memo/v1.txt`.
- Tables: 0830's `preparer_memos`, `preparer_memo_versions`, `preparer_memo_events` (no
  migration). Matrix: none (the agent writes only its draft version; L1/L2 stay people's).
- Tests: `backend/tests/unit/tax/test_t05t48_memo_drafter.py`; the fake-model suite
  `evals/tax_memo_drafter` (T-05-T30) runs in the end pass's evals-fast lane.
- Rollback: revert; no row is written unless a run calls `draft_memo`.

## Partial
- The prompt variant flag `prompt.tax.memo_drafter` and the suite registration in
  `_eval_suites.py` are T-05-T47 (this sprint, after this row).
- Who starts a draft (the memo routes `POST …/memo/draft`, the run step) and adopt/approve and
  staleness are T-05-T54 (S42); real-model parity is T-05-T64's clearance.

## Progress log
- 2026-11-13: built; spec codegen run; tests written, not run.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-4708 | inputs, settlement and storage of the drafter | no |
