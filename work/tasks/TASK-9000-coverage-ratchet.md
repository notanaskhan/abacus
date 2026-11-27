---
id: TASK-9000
title: "F-01-T05: CV-1 total coverage never drops (S54 coverage back-fill)"
spec: SPEC-000
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: amber
status: in-review
branch: s54-cv1-coverage-ratchet
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-26
updated: 2026-11-26
plan_key: F-01-T05
---

## Objective
DEC-6003 CV-1: a pull-request check that fails when total coverage drops below what main recorded, so the S54 back-fill only moves one way while the total is under the floor.

## Done
- backend/src/abacus_tools/ci/coverage_ratchet.py: stage-1 guard (record well formed, never lowered or removed against origin/main) and stage-2 --measure (combined total to two decimals not under the record; asks for a raise above +0.5)
- backend/coverage-baseline.toml: 80.50 from main CI run 45518852575 (df6b9c15f, reported 81%)
- Makefile: guard in check-fast, --measure in ci-coverage before coverage_floor
- docs/architecture/protected-paths.md: the baseline listed
- tests/unit/tools/test_coverage_ratchet.py: 29 cases (parse refusals, lower/remove refusal, judge boundary, raise advice, total parsing)
- DEC-6005

## Progress log
- `2026-11-26` — Built; 29 unit cases pass. The first CI measurement with --precision=2 raises the record (CV-2 does).
