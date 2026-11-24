---
id: TASK-8910
title: "T-06-T41: Workbook-run step registration (live path)"
spec: SPEC-000
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: amber
status: in-review
branch: s53-t06t41
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-23
updated: 2026-11-23
plan_key: T-06-T41
---

## Objective
depreciation_register, bonus_eligibility and apportionment_ptet activities into T-05's WorkbookRunWorkflow behind workflow.patched with replay histories; RecomputeWorkflow dirty-set edges (asset change to 8825 to Schedule K; sourcing to credits; section 754 to basis); tie_out_check rules for sheets 02 and 08. Acceptance: replay of the pre-change histories passes, and an approved asset change re-runs only the depreciation and K-1 steps.

## Done
- run_steps.py live path: depreciation_register writes 02 from the T-06-T33 register through E3 (A no, B description, C placed in service, D cost, F current year, G bonus %, a footing Total row), bonus_eligibility reads E3's bonus check (check/not_eligible → Needs attention bonus_check), apportionment_ptet first writes 08 from the approved sourcing and PTET paid (states_service.approved_states); without register assets or an approved sourcing the imported-report path (T-05) is unchanged
- entity_run_plan.RECOMPUTE_EDGES + steps_for_change + rerun_for: an approved asset change re-runs depreciation, bonus, capital and the K-1s; an approved sourcing re-runs apportionment and the K-1s; fixed_assets_service.settle_change and states_service.approve_sourcing start it as the approver
- entity_sections.sheet_tie_outs: fa_foots (02 to its Total) and state_k1_sum (08's state shares to 06's state column), in tie_out_check after every run
- tests/workflows/test_t06t41_workbook_run_replay.py (every agent-run-v2 history replays), tests/unit/tax/test_t06t41_run_step_registration.py

## Progress log
- `2026-11-23` — Built in the S53 sequential stack (DEC-5912).

## Plan (amber)
1. Live branches in the three step handlers; recompute edges and re-run hooks; 02/08 tie-outs.
2. No workflow code changes: steps are activities dispatched by kind, so no `workflow.patched`; replay test over the committed v2 histories.
3. Rollback: revert the handlers (the imported path stays); no schema change.
