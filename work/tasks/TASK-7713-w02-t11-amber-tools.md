---
id: TASK-7713
title: W-02-T11 Amber tools tax.season_counts, binders.read, workpapers.read_section, assurance.read_materiality
plan_key: W-02-T11
spec: SPEC-653
acceptance_criteria: [AC-A6]
risk_zone: amber
status: in-review
branch: w02-t11-amber-tools
worktree: /Users/ayushkbhatia/Accrued/abacus-s41
created: 2026-11-13
updated: 2026-11-13
---

## Objective
Four C17 tools the Workbench assistant needs, each with its description prompt, counts by code,
and nothing `tri`.

## Plan (amber)
- `tax/tools.py` (season counts), `requests/agent_tools.py` (binders), new
  `workpapers/workbench_tools.py` and `assurance/workbench_tools.py` (imported by their apis),
  four prompts `ai_gateway/prompts/tool.<name>/v1.txt`, `docs/contracts/tool-registry.md`.
- Tests: `backend/tests/unit/workbench/test_w02t11_amber_tools.py`.
- Rollback: revert; the assistant's spec (W-02-T12) loses them.

## Partial
- `tool_selection` is the workbench_assistant suite's (W-02-T07 cases; W-02-T12 runs it).
- S41 gaps (DEC-4734): AC-A6's "Binders 241" is `binders.read`'s `season_total`, the season's
  visible binders counted by code over BND-01's index, with `by_status` tiles.

## Progress log
- 2026-11-13: built; registration verified at import; tests written, not run.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-4716 | the four tools' shapes and homes | no |
