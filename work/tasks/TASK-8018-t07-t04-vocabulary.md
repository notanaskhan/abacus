---
id: TASK-8018
title: "T-07-T04: glossary and status-vocabulary rows for trusts and estates"
spec: SPEC-656
acceptance_criteria: []
risk_zone: red
status: in-review
branch: t07-t04-vocabulary
worktree: /Users/ayushkbhatia/Accrued/abacus-s44
created: 2026-11-14
updated: 2026-11-14
plan_key: T-07-T04
---

## Objective
glossary and status-vocabulary rows for trusts and estates.

## Plan
Files: `docs/product/glossary.md` (new section), `docs/product/status-vocabulary.yaml` (instrument_interpretation, instrument_segmentation, sixty_five_day_election, estate_inventory_item, estate_deduction_election, fiduciary_computation_label), regenerate `_statuses.py` and `status.gen.ts`; copy lint rule rejecting "Ties" on TXT-02 and TXT-04. Test: `tests/unit/tax/test_t07t04_vocabulary.py`.

## Progress log
- `2026-11-14` — Built. Glossary section, six status objects, regenerated `_statuses.py` and `status.gen.ts`, the "Ties" ban in `copy-bans.test.ts`, `tests/unit/tax/test_t07t04_vocabulary.py` (not run; end pass).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
