---
id: TASK-8072
title: "C-01-T31: Eval suite evals/close_agent, thresholds frozen before T29's prompts (protected)"
spec: SPEC-655
acceptance_criteria: [AC-1]
risk_zone: red
status: in-review
branch: c01-t31-close-agent-evals
worktree: /Users/ayushkbhatia/Accrued/abacus-s46
created: 2026-11-15
updated: 2026-11-15
plan_key: C-01-T31
---

## Objective
Write and freeze `close.agent`'s evaluation suite before any prompt work: cases per mode, graders
for every dangerous error of chapter 05 §5.5.3, seeded failures, and the fast subset in CI.

## Plan (red: protected eval suite)
1. `abacus_tools/evals/close_agent.py`: `FROZEN` thresholds, case models, ten graders,
   `run_suite` with dangerous-error coverage (≥ 5 each) and seeded-grader coverage, signed report.
2. **Protected** `evals/close_agent/suite.yaml` (61 cases: 51 graded, 10 seeded), generated
   deterministically by `abacus_tools/evals/close_agent_cases.py`. Needs Ayush's approval.
3. `__main__.py` `--agent close_agent`; `make evals-close-fast|full`; CI `evals-fast` step.
4. `tests/unit/evals/test_c01t31_close_agent_suite.py`.
Rollback: revert; nothing consumes the suite until C-01-T29.

## Progress log
- `2026-11-15` — Planned at the S46 kickoff (#2053).
- `2026-11-15` — Built (DEC-5059). The suite and its unit tests pass locally (8 passed).
- Open: `evals/baselines.yaml` rows for `close.agent` arrive with the capability's budgets (T29,
  real runs T32); labels stay `pending_cpa` until the CAS CPA signs.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-5059 | Ten graders over recorded outputs; fact tokens; dual-threshold rule in the grader | no |
