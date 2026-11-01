---
id: TASK-2924
title: P-04-T37 golden-figure tests for the review scenario
spec: SPEC-600
acceptance_criteria: [P-04-T37]
risk_zone: amber
status: in-review
epic: P-04
plan_key: P-04-T37
branch: s24-p04-t37 (on s24-p04-t36)
worktree: /Users/ayushkbhatia/Accrued/abacus-s24
created: 2026-11-02
updated: 2026-11-02
---

## Objective

ADR-078 goldens for the review scenario: 252,200 / 189,150 / 12,610; 155,000 / 116,250 / 7,750; Feld net change 0; Trial Balance 14 of 14 cited; Ridgeline 11 open issues; DF-34 timeline.

## Acceptance (backlog)

The golden suite passes on the loaded scenario and fails on any figure that does not foot.

## Plan (amber)

- `backend/tests/golden/review/review_scenario.yaml`: cases transcribed from P-04 §2/§3, SHL-11, SHL-12, SHL-16, TXP-10, DF-34 and A-02 §5.3, each with its source; numbers as text.
- `backend/tests/golden/review/test_p04t37_review_golden.py`: materiality through A-04's engine; sums and differences as Decimal; probes into the scenario package (Northwind TB benchmark, Granite pre-tax income, the slice's 5 + 6 issues, DF-34's 10:02 / 11:12 events); a one-dollar-off case proves the teeth.
- No production code, no migrations.

## Progress log

- 2026-11-02: built; tests written, not run. The loaded-state reads (card figures from the DB after `--slice review`, 14 of 14 on the RA workpaper, Feld's checkpoint 6 diff) wait on DEC-1969's owners; here those three are arithmetic identities documenting the figure.
