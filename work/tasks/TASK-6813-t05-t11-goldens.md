---
id: TASK-6813
title: "T-05-T11: Golden fixtures transcribed (ADR-078) into backend/tests/golden/tax_entity/ and backend/tests/golden/workpapers/: TB pipeline, Ridgeline allocation, Harborview waterfall, Schedule K and K-1, capital and M-2, formula DAG and tie-outs"
spec: SPEC-651
acceptance_criteria: [AC-14]
risk_zone: amber
status: in-review
branch: s36-t05-t11
worktree: /Users/ayushkbhatia/Accrued/abacus-s36
created: 2026-11-11
updated: 2026-11-11
plan_key: T-05-T11
---

## Objective
Every figure in section 1 of the spec is an exact-Decimal golden case, and the Schedule L conflict
is encoded as DF-34 decided it.

## Built
- `backend/tests/golden/tax_entity/ridgeline_ty2025.yaml`: TB pipeline (TXP-02's 28 accounts and
  the §1 totals), Schedule L as DF-34 decided (1200 → L5, 2500 → L18, 2000 split from 2050),
  Ridgeline allocation (two periods of 628,100, partner totals), Schedule K lines and the Pell
  Street Ventures crossfoot (400,270 = 35% × 615,800 + 30% × 615,800), capital and M-2 (331,405 =
  2,319,835 × 5/35; §743(b) 28,595; the 6,200 fix; row 12 to 1,914,050), Harborview waterfall
  (rungs, targets, plugs, the 20% catch-up). Each case: source, parameter set ty2025, reviewed_by
  pending the tax CPA.
- `backend/tests/golden/workpapers/formula_dag.yaml`: I18 (94,000) and row 12 with H12.
- Tests beside each golden run the existing engines (TB pipeline, allocation, DAG) against them and
  foot the rest in exact Decimal.

## Progress log
- `2026-11-11` — Built (S36). Tests written, not run (end pass).

## Partials
- Solo edition: transcribed by the same builder (SOLO-RULES drop the second person; ADR-078 as
  amended: from the spec and the blueprint, before the engines were read).
- Schedule K, K-1 and waterfall engines are later rows: those cases foot only, until their engines
  land and run against them. The CPA's signed memos are M18's.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-3410 | Golden layout, pending reviewer, foot-only until an engine exists | no |
