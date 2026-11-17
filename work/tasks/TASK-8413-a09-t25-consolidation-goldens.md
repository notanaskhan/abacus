---
id: TASK-8413
title: "A-09-T25: Golden tests for the consolidation engine"
spec: SPEC-658
acceptance_criteria: [AC-3]
risk_zone: red
status: in-review
branch: a09-t25-consolidation-goldens
worktree: /Users/ayushkbhatia/Accrued/abacus-s48
created: 2026-11-17
updated: 2026-11-17
plan_key: A-09-T25
---

## Objective
Spec section: docs/plan/epics/A-09.md §9.2 (ADR-078; implementer N, author AY). Goldens for the consolidation engine: rows foot and columns net to zero, 50,760,000, 48,640,000 asset eliminations, Dr = Cr, net income 3,500,000, Level 2 39,760,000 and 4,760,000, attribution 27,000,000 + 12,760,000 + 8,400,000 + 2,600,000; Hypothesis properties; the reviewed_by memo reference.

## Plan (red)
1. `tests/golden/ledger/consolidation/harlow_pike_fy2026.yaml`: the golden figures with `reviewed_by` (memo `GRM-A09-CONSOLIDATION-01`, chapter 10 §10.9.4, pending CPA signature).
2. `tests/golden/ledger/consolidation/test_a09t25_consolidation_golden.py`: Level 1 and Level 2 goldens, asset eliminations, debits equal credits, attribution foots; Hypothesis: removing any posted elimination changes a level's totals, and any balanced reclass keeps columns at zero and rows footing. Inputs are A-09-T19's seed figures (loaded from its test module, one copy).

## Progress log
- `2026-11-17` — Written in the S48 sequential stack; ruff clean; not run (end pass). The 67,840,000 Dr = Cr golden is recorded in the fixture and the test asserts debits equal credits on the consolidated column; the end pass checks the figure itself against AUD-33 a. Gates and tests run once at the S48 end pass (build first, test last).
