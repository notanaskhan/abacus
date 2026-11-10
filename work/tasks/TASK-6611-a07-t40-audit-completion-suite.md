---
id: TASK-6611
title: "A-07-T40: Deterministic conformance suite evals/audit_completion/suite.yaml (code-only graders)"
spec: SPEC-644
acceptance_criteria: [AC-40]
risk_zone: amber
status: in-review
branch: s34-a07-t40
worktree: /Users/ayushkbhatia/Accrued/abacus-s34
created: 2026-11-10
updated: 2026-11-10
plan_key: A-07-T40
---

## Objective
The suite passes at 1.0 on every threshold and fails when a seeded narration claims 'approved' or
a digest card cites an undecided card.

## Plan (amber)
1. `evals/audit_completion/suite.yaml` (new, PROTECTED thresholds): 21 cases on Northwind and
   Granite Peak over five graders: count equality, citation (coverage 1.0), reserved actions
   absent, narration lint (the AgentBlocks check: human-act claims, free numbers) and containment
   (hostile file names and minutes stay inside one `<untrusted>` block).
2. `abacus_tools/evals/audit_completion.py` (new): the code-only runner; refuses a suite that
   drops its negative cases; `python -m abacus_tools.evals --agent audit_completion`;
   `make evals-completion-fast`.
3. Tests: `tests/unit/evals/test_a07t40_audit_completion.py`.

## Progress log
- `2026-11-10` — Built and run once while writing it (deterministic, no model): passed at 1.0.
  The unit tests run at the end pass. CI wiring of the target into the evals job is an end-pass
  check.
