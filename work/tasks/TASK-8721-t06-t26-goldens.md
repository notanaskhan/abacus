---
id: TASK-8721
title: "T-06-T26: Goldens for E10, E11 and E12 (TXP-13)"
spec: SPEC-702
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
branch: t06-t26-goldens
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-19
updated: 2026-11-19
plan_key: T-06-T26
---

## Objective
tests/golden/tax_entity_depth/other_entities_figures.yaml with sources and test_t06t26_other_entities.py: Bluestem 1,488,200 split 1,041,740 / 446,460, Ashford 2,257,200 at 28.9%, Lakeshore's Part IX 4,014,000 at 80.0%, plus footing properties (distribution columns, per-share split).

## Plan (amber)
1. Golden figures file and tests (ADR-078 independent author, solo edition).

## Progress log
- `2026-11-19` — Built; 5 pass. Gaps recorded, not invented: Lakeshore's 87.4% public support (no source table, T-06-T18), the TAX-11 Item F/I/J/K checks and the 121/5/2 hand-off preview counts (pinned with the form-preview diagnostics and hand-off tasks); Ashford's pretax and Lakeshore's three Part IX columns are synthetic, labelled so. Gates and tests run once at the S51 end pass (build first, test last).
