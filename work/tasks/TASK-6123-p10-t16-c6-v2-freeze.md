---
id: TASK-6123
title: "P-10-T16 C6 v2 freeze: contract section complete and the frozen OpenAPI snapshot"
spec: SPEC-000  # row (P-10-T16)
acceptance_criteria: [AC-1]
risk_zone: amber
status: done
epic: P-10
plan_key: P-10-T16
branch: s30-p10-t16
worktree: /Users/ayushkbhatia/Accrued/abacus-s30
created: 2026-11-08
updated: 2026-11-08
---

## Objective
The v2 section of docs/contracts/agent-runs.md complete (callers, status words, human-only actions, audit events) and a frozen OpenAPI snapshot.

## Plan
- `abacus_tools/contracts.py`: `c06_v2` lists the v2 route models (runs, plans, questions, commands, feedback, auto mode, capabilities, sessions, stream topics, usage).
- `backend/tests/contracts/c06_v2/v2.json`: frozen with `--freeze c06_v2 v2`.
- `docs/contracts/agent-runs.md` §9.1: snapshot rule, callers table, status words, human-only actions, audit events.

## Progress log
- 2026-11-08: built. Generated the snapshot; nothing run (tests at the end review). ruff clean.

## Decisions made during this task
DEC-2713
