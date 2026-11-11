---
id: TASK-7313
title: "P-10-T48: Independent AC and property tests (ADR-078) for the run workflow, commands, proposals bridge and engagement run (T29, T32, T33, T38, T39)"
spec: SPEC-647
acceptance_criteria: [AC-W1, AC-W2, AC-W3, AC-W7, AC-P6, AC-E1]
risk_zone: red
status: in-review
branch: s37-p10-t48
worktree: /Users/ayushkbhatia/Accrued/abacus-s37
created: 2026-11-12
updated: 2026-11-12
plan_key: P-10-T48
---

## Objective
Property tests over random event sequences find no path to a terminal state without its
prerequisites and no agent-actor decision row.

## Plan
- `backend/tests/unit/agents/test_p10t48_independent.py` (Hypothesis, from SPEC-647): random DAG
  plans and outcome sequences: at most three running, no step before its dependencies, no
  terminal aggregate while a step runs or waits; reserved and undeclared writes refused before
  approval; empty and unknown-kind plans refused; AC-E1's 14 = 1 + 5 + 1 + 4 + 3.
- `backend/tests/integration/test_p10t48_human_only.py`: `agent_plans.decided_actor_kind` and
  `run_sign_offs.actor_kind` CHECKs bound to the session GUCs; no UPDATE or DELETE for the app
  role; the matrix denies agent and system every run decision.
- Replay: the S35 and S36 history suites already pin AgentRunWorkflow, ApprovedWriteWorkflow and
  the engagement run (no new history).

## Partial
- Grant timing and Undo (AC-P1, AC-P2) and via-Agent attribution are covered by P-10-T38's
  integration suite; an independent end-to-end run of them needs the worker (P-10-T49, S38).

## Progress log
- `2026-11-12` — Written (S37). Run at the end pass.
