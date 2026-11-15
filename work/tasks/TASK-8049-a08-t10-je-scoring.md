---
id: TASK-8049
title: "A-08-T10: JE scoring compute library v1 (sampling/compute/je_scoring.py)"
spec: SPEC-657
acceptance_criteria: [AC-0.9, AC-1.2, AC-1.3]
risk_zone: red
status: in-review
branch: a08-t10-je-scoring
worktree: /Users/ayushkbhatia/Accrued/abacus-s45
created: 2026-11-15
updated: 2026-11-15
plan_key: A-08-T10
---

## Objective
Pure JE scoring: the five criteria evaluators, score with reason codes, unique flagged count,
deterministic ordering, `engine_version` and `inputs_hash`.

## Plan (red: protected compute path)
1. `sampling/compute/je_scoring.py` (stdlib only, the compute import contract).
2. `tests/unit/sampling/test_a08t10_je_scoring.py`: the seed hits on a built population,
   availability, determinism, hash, every branch, a Hypothesis property.
Rollback: revert; nothing reads it until A-08-T12.

## Progress log
- `2026-11-15` — Planned at the S45 kickoff (TASK-8029) as "the rest of the partial" (SPEC-037's
  `selection.py` rules exist; this adds holiday, post-close, role, score and the hash).
- `2026-11-15` — Built (DEC-5034). ruff and pyright clean; a one-off run reproduced 142 · 38 · 61 ·
  17 · 9 → 236 (177 without the JE fields). Tests and the 100% branch-coverage check run at the
  end pass.
