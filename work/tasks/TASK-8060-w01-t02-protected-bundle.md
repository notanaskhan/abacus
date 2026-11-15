---
id: TASK-8060
title: "W-01-T02: Connect protected bundle (matrix, two flags, status rows, glossary, agents→integrations)"
spec: SPEC-659
acceptance_criteria: [AC-7, AC-8]
risk_zone: red
status: in-review
branch: w01-t02-protected-bundle
worktree: /Users/ayushkbhatia/Accrued/abacus-s45
created: 2026-11-15
updated: 2026-11-15
plan_key: W-01-T02
---

## Objective
The bundle every W-01 row builds on, with both founders' approval in the plan.

## Plan (red)
1. **Protected** `permission-matrix/integrations.yaml` (nine actions); regenerate.
2. **Protected** new `feature-flags/integrations.yaml` (two flags).
3. **Protected** `status-vocabulary.yaml`, `glossary.md`.
4. **Protected** `banned_patterns.py` MODULE_DEPENDENCIES: `agents → integrations`.
Rollback: revert.

## Progress log
- `2026-11-15` — Planned at the S45 kickoff (#2010).
- `2026-11-15` — Built (DEC-5045). Codegen clean. Import-linter and the generated matrix tests run
  at the end pass. **Needs:** both founders' approval (the plan); Ayush approves here.
