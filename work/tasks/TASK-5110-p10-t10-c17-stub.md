---
id: TASK-5110
title: P-10-T10 C17 agent tool registry stub, registry check and TOOL-001
spec: SPEC-000  # row (P-10-T10)
acceptance_criteria: [AC-1]
risk_zone: red
status: in-review
epic: P-10
plan_key: P-10-T10
branch: s29-p10-t10
worktree: /Users/ayushkbhatia/Accrued/abacus-s29
created: 2026-11-06
updated: 2026-11-06
---

## Objective
The tool contract: @agent_tool, four kinds, the fail-closed slot, and final verbs refused at three layers.

## Plan
agents/tools/registry.py; abacus_tools/quality/tool_registry.py in check-fast; TOOL-001; docs/contracts/tool-registry.md. No tool is registered. Rollback: revert.

## Progress log
- 2026-11-06: built. `backend/tests/contracts/c17_tools/test_c17_stub.py` written, not run (end pass). `quality.tool_registry` run: passes on an empty registry.

## Decisions made during this task
DEC-2409
