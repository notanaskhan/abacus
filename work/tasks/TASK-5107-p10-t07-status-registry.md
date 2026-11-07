---
id: TASK-5107
title: P-10-T07 status words for run steps, plans and questions, and glossary rows
spec: SPEC-000  # row (P-10-T07)
acceptance_criteria: [AC-1]
risk_zone: red
status: in-review
epic: P-10
plan_key: P-10-T07
branch: s29-p10-t07
worktree: /Users/ayushkbhatia/Accrued/abacus-s29
created: 2026-11-06
updated: 2026-11-06
---

## Objective
Registry and glossary words the runtime's contracts and SHL-13, WB-03 need.

## Plan
status-vocabulary.yaml objects agent_run_step, agent_plan, agent_question; the 14 run states and workbench_session were already there. Glossary: run sign-off, agent feedback, session item. Regenerate.

## Progress log
- 2026-11-06: built. `make regenerate` passes the vocabulary's own lint. Pinned counts in the end pass.

## Decisions made during this task
None.
