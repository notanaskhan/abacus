---
id: TASK-3259
title: N-04-T11 notice analysis (return as filed, proposed items, code comparison, notice_position card, notes)
spec: SPEC-000  # row (N-04 has no SPEC yet)
acceptance_criteria: [AC-11]
risk_zone: amber
status: in-review
epic: N-04
plan_key: N-04-T11
branch: s27-n04-t11
worktree: /Users/ayushkbhatia/Accrued/abacus-s27
created: 2026-11-04
updated: 2026-11-04
---

## Objective
"The Whitley analysis shows 412 to 3,532, two cited 1099-INTs not on the return, an agreeing
bracket check and a decision card reserved to Daniel Reyes with Agree preselected only when the
agent is live."

## Plan (amber)
- `notices/analysis.py`: return-as-filed snapshots (cited lines, insert-only), proposed items
  (cited entry), `run` (compute library: `underreporter.compare`, `bracket.check`; insert-only
  `notice_analyses` version, idempotent on `inputs_hash`), the agent-step hook (fails closed;
  a recommendation only from `live`), `notice_position` card reserved to the signer with code's
  options and an applier recording the position, decision requests and sealed notes.
- `notices/contract.py`: the six analysis routes live; `notices/api.py` registers the kind.
- Error catalogue (2) and client regenerated.
- Tests: `tests/unit/notices/test_n04t11_analysis.py`.
- Partial (recorded): the analysis runs in the request, not yet as the background
  `NoticeAnalysisWorkflow`; the T-01 transcript segment rows and the word-layer location of each
  payer amount (`document_text` citations) wait on N-04-T16's agent step and T-01-T45's
  comparisons read; the CCH-import source of the snapshot is recorded as `engine_import` by the
  person who adopts it.

## Progress log
- 2026-11-04: built.

## Decisions made during this task
DEC-2239.
