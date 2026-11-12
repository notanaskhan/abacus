---
id: TASK-7622
title: T-05-T32 run step handlers part 1 (tax/run_steps.py)
plan_key: T-05-T32
spec: SPEC-651
acceptance_criteria: [AC-F2, AC-F3, AC-F6, AC-F7]  # Run 2 on the seed 10 of 10 with 11 open items; K-1 drafts never portal-visible
risk_zone: amber
status: in-review
branch: t05-t32-run-steps
worktree: /Users/ayushkbhatia/Accrued/abacus-s40
created: 2026-11-12
updated: 2026-11-12
---

## Objective
The first five workbook run handlers on P-10's run-step slot, computing by code and writing cells
through `write_cells`, never over a person's value.

## Plan
- `tax/run_steps.py` (new): `import_trial_balance` (newest C9 trial balance → 01: code, name, UTB,
  AJE, RJE, ATB as a formula, column totals; `trial_balance_missing`, `token_expired`),
  `map_lines` (mapped lines → 03; unmapped counted, the export gate's), `contributions_distributions`
  (05 C and D → 07 rows 2 and 6), `capital_m2` (05 F per partner and 07 B9), `federal_k1s` (09
  per recipient from 06 × the ownership note's share). Each writes in one unit of work audited
  `workbook.step_written`; `_kept` drops writes over human cells (`latest_sources`).
- Part 2 kinds registered as `import_required` (Needs attention) until T-05-T40.
- `tax/entity_run_plan.py`: each step's arguments name the return (`return_id`).
- `agents/engagement_run.py` (protected): run-step kinds may hold digits after the first letter.
- Registered at the tax api's import. Test `backend/tests/unit/tax/test_t05t32_run_steps.py`.
- Rollback: revert; the run start answers `run_step_unavailable` again.

## Deviations (DEC-4617)
- The K-1 drafts are workbook cells (09 K-1s), not `k1_packages` rows: no package is created here,
  so nothing can reach a portal principal; T-02's package flow takes the drafts at release.
- The capital and M-2 inputs are sheet 05's partner rows (beginning, contributions, distributions,
  income share), entered by import or a person; with none the steps fail `capital_inputs_missing`.
- `token_expired` maps a connection's refusal surfaced as `PermissionError`; the connection layer's
  own error class lands with T-01's live connector.

## Partial
- "Run 2 completes 10 of 10 with 11 open items" needs the part-2 handlers (T-05-T40) and the seeded
  Ridgeline inputs; measured with T-05-T65's independent suite.

## Progress log
- `2026-11-12` — Part-1 handlers built (DEC-4617). Tests at the S40 end pass.
