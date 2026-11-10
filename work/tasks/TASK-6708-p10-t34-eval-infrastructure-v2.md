---
id: TASK-6708
title: "P-10-T34: eval infrastructure for runtime v2: trajectory and conversation case formats, twelve graders, the trajectory fast subset in stage 3, taxonomy additions"
spec: SPEC-647
acceptance_criteria: [AC-W1]
risk_zone: red
status: in-review
branch: s35-p10-t34
worktree: /Users/ayushkbhatia/Accrued/abacus-s35
created: 2026-11-10
updated: 2026-11-10
plan_key: P-10-T34
---

## Objective
Each grader catches a seeded failing case, and a PR changing a `tool.<name>` prompt runs the trajectory fast subset in stage 3.

## Plan (red)
1. `abacus_tools/evals/trajectory.py` (new): Pydantic case formats (`Trajectory`, `Turn`, `Case` of
   kind trajectory or conversation, `Expected`), the twelve deterministic graders, `grade_case`
   (seeded failures must fail, everything else must pass), `run_suite` (full and fast), signed
   report, `changed_tool_prompts`.
2. `evals/agent_trajectories/suite.yaml` (new, protected thresholds): a passing Northwind
   materiality trajectory, one seeded failing case per grader (two for args_valid), a full-only
   case and a two-turn conversation.
3. CLI `--agent agent_trajectories`, `make evals-trajectory-fast`, and the CI stage 3 step (the
   `agents` path set already covers `ai_gateway/prompts/tool.*`).
4. Taxonomy: `taxonomy.TRAJECTORY_CATEGORIES` and the protected doc's "Agent trajectory failures"
   section (bullets, so the screening and adversarial table sets are unchanged).
5. `agents.api` exports `has_never_verb` so the reserved-action grader uses the plan's own rule.
6. Tests: `tests/unit/tools/evals/test_p10t34_trajectory.py`.

## Progress log
- `2026-11-10` — Built; tests written, not run (end pass). The acceptance names AC-W1 as the
  nearest SPEC-647 criterion (reserved actions refused); SPEC-647 §6 has no AC id of its own.
