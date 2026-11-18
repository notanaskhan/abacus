---
id: TASK-8630
title: "T-06-T19: Golden fixtures and property cases for E3, E4, E8 and E9"
spec: SPEC-702
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
branch: t06-t19-goldens
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-18
updated: 2026-11-18
plan_key: T-06-T19
---

## Objective
Spec section: docs/plan/epics/T-06.md §10 (I-CLOCKS goldens), ADR-078. Every figure in the TXP-03, TXP-04, TXP-08 and TXP-09 contracts as a golden case with source, screen, state and parameter_set; a seeded off-by-one in any engine fails at least one case.

## Plan (amber)
1. backend/tests/golden/tax_entity_depth/tax_entity_depth_figures.yaml: e3_register, e4_m3, e4_m2, e8_basis, e9_states with their source, screen, state and parameter set; amounts as quoted Decimal text.
2. test_t06t19_goldens.py: exact equality per case, plus Hypothesis properties (752 shares and PTET credits always foot; an M-3 row ties both ways) that an off-by-one breaks.

## Progress log
- `2026-11-18` — Built in the S50 sequential stack (DEC-5630). The ADR-078 separate author is the solo builder (AMENDMENT-solo); goldens are transcribed from the handoff specs, not from the engines. Not run: the end pass. Gates and tests run once at the S50 end pass (build first, test last).
