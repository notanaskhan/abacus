---
id: TASK-8959
title: "Q-03-T367: Quarterly mutation sweep: close and JE-scoring compute"
spec: SPEC-000
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: amber
status: in-review
branch: s53-mutation-sweeps
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-24
updated: 2026-11-24
plan_key: Q-03-T367
---

## Objective
Each compute package meets 85% killed.

## Done
- mutation runs include tests/golden (DEC-5942): the goldens are pure and are what kills a compute package's mutants
- survivor triage, new tests: canonical hashes pinned with per-field sensitivity (reconciliation, schedules, JE scoring, JE selection), the CAS package's figures whole, the reconciliation engine's edges and one whole period, the schedules' edges, JE selection's edges
- local run (mutmut 3.8.0, 2,242 mutants): information_returns 97.2%, package 94.3%, reconciliation 92.6%, schedules 97.3%, je_scoring 87.0%, je_selection 96.3% (93.1% overall; before: 52.3%, package 3.3%)
- finding ED-331 (open, owner C-01): a prior bank-side bank_error is dropped by reconcile

## Progress log
- `2026-11-24` — 2026-11-24: met locally. The compute scope's floor (74) covers every compute package; mutation-weekly measures it on main.
