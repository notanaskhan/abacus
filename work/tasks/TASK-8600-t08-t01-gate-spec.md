---
id: TASK-8600
title: "T-08-T01: Gate check, SPEC-710 tax season and practice tools, and six screen contracts"
spec: SPEC-710
acceptance_criteria: [AC-1]
risk_zone: green
status: in-review
branch: t08-t01-gate-spec
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-18
updated: 2026-11-18
plan_key: T-08-T01
---

## Objective
Spec section: docs/plan/epics/T-08.md §0.1, §2, §3, §11.2. Gate check of table 0.1 on main; SPEC with numbered ACs; screen contracts for ENG-07, HOME-03, TAX-10, TAX-14, TAX-15, TAX-16 (33 artboards plus composed states) with persona, clock, scenario, parity tier and deviations; answer OQ-1..OQ-17.

## Plan (green)
1. `docs/specs/SPEC-710-…md`: gate table (every red row accepted; ADR-232 proposed, polling first; P-25 not drafted so TAX-15 raise stays template-only), OQ-1..OQ-17 answers, AC-1..AC-40, S50 task map.
2. Six screen contracts generated from the handoff READMEs (artboards and link graph) with T-08 §5.4 scenarios and the deviations of §2.1 and §11.2.

## Progress log
- `2026-11-18` — Built in the S50 sequential stack (DEC-5600). Docs only. Gates and tests run once at the S50 end pass (build first, test last).
