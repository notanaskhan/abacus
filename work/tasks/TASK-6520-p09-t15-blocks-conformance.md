---
id: TASK-6520
title: "P-09-T15 finish: the AgentBlocks conformance suite in the eval runner, CI and a signed report"
spec: SPEC-648
acceptance_criteria: [AC-6]
risk_zone: red
status: in-review
branch: s33-p09-t15
worktree: /Users/ayushkbhatia/Accrued/abacus-s33
created: 2026-11-09
updated: 2026-11-09
plan_key: P-09-T15
---

## Objective
The suite scores 1.0 on every case on every repeat, a seeded regression removing one lint rule
fails it, and the HMAC-signed report publishes. TASK-5006 wrote the corpus
(`evals/agent_blocks/suite.yaml`); this row runs it as an eval.

## Plan
1. `abacus_tools/evals/agent_blocks.py`: load, run every case through the gateway's
   `run_output_check("agent_blocks", …)` per repeat, per-category and overall rates against
   `required_pass_rate`, HMAC-signed JSON report to `--out`.
2. `python -m abacus_tools.evals --agent agent_blocks`; `make evals-blocks-fast`; CI stage 3 step on
   agent paths (`abacus_tools.ci.paths.AGENTS` covers `blocks.py` and `output_checks.py`).
3. Tests: 1.0 on every repeat, a removed lint rule fails, the signed report.
Rollback: revert.

## Progress log
- `2026-11-09` — Built; tests written, not run (end pass). `evals/baselines.yaml` takes no entry: it
  holds real-model cost baselines and this suite makes no model call (DEC-3120).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-3120 | No cost baseline for a code-only suite; CI step on agent paths | no |
