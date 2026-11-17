---
id: TASK-8510
title: "T-06-T01: Gate check, SPEC-702 entity return depth, relationships and hand-offs, and eight screen contracts"
spec: SPEC-702
acceptance_criteria: [AC-1]
risk_zone: green
status: in-review
branch: t06-t01-gate-spec
worktree: /Users/ayushkbhatia/Accrued/abacus-s49
created: 2026-11-17
updated: 2026-11-17
plan_key: T-06-T01
---

## Objective
Spec section: docs/plan/epics/T-06.md §0.1, §2, §3, §11.2. Gate check; SPEC with numbered ACs; screen contracts for TXP-03, TXP-04, TXP-08, TXP-09, TXP-13, TAX-11, CLI-03, AUD-38 (44 artboards) with persona, clock, parity tier and DV-1..DV-14; record what T-05 shipped.

## Plan (green)
1. `docs/specs/SPEC-702-…md`: gate table (all ADRs accepted; CLI-03 board T-06-T68 not made), T-05 seams with paths (entity_run_plan.py steps, run_steps.py, compute/entity/capital.py ScheduleM2, entity_issues.py, tb_pipeline.py, parameters/ty2027.yaml), OQ-1..OQ-9 answers, the P-63 graph semantics, AC-1..AC-36.
2. Screen contracts: eight files, every artboard listed as built with its scenario, persona and clock; deviations DV-1..DV-14 placed on their screens.

## Progress log
- `2026-11-17` — Built in the S49 sequential stack (DEC-5510). Docs only. CLI-03's composed states (Add relationship sheet, edit, end) wait on the CLI-03 board (T-06-T68), so T-06-T02 stays blocked. Gates and tests run once at the S49 end pass (build first, test last).
