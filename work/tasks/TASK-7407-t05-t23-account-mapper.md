---
id: TASK-7407
title: "T-05-T23: tax.account_mapper capability: prompt tax.map_accounts@v1 through ai_gateway, inputs limited to account codes and names (no amounts), output constrained to published form-line keys or abstain, suggestions become mapping proposals through C17 propose tools; client_data none until cleared"
spec: SPEC-651
acceptance_criteria: [AC-1]
risk_zone: red
status: in-review
branch: s38-t05-t23
worktree: /Users/ayushkbhatia/Accrued/abacus-s38
created: 2026-11-12
updated: 2026-11-12
plan_key: T-05-T23
---

## Objective
The mapper suggests a published Form 1065 line key per account from its code and name, or
abstains; code keeps only published, confident answers, and a person approves them in SHL-10.

## Plan (red)
- Spec `specs/v2/tax.account_mapper.yaml` (compiled into `_specs_v2.py`): small tier, prompt
  `tax.map_accounts@v1`, `client_data: none`, suite `evals/tax_account_mapper`, one propose tool.
  Shape `workflow`, not `single_call`: a v2 single_call lists no tools and the row's proposals go
  through C17 (DEC-4406).
- Prompts `tax.map_accounts/v1.txt`, `tool.tax.propose_account_mappings/v1.txt`.
- `tax/account_mapper.py` (red): `model_input` (codes and names, amounts redacted, unique),
  `settle` (published keys only; abstentions coded: no answer, abstained, answered twice, key not
  published, confidence out of range or under 0.5), `map_accounts` (one gateway call with the
  partnership as the §7216 subject, then one proposal through C17).
- C17 tool `tax.propose_account_mappings` (tri, `proposal.create`): one row per account on the
  return (`tax_account_mapping`, `account:<code>`), registered as a suggestion target.
- Tests: `tests/unit/tax/test_t05t23_account_mapper.py` (12 pass), including the S37 suite's
  recorded outputs settling to their labels.
- Rollback: revert; the capability is dark (`client_data: none`).

## Partial
- Applying an approved mapping writes ledger's `account_mappings.form_line_key`, which is T-05-T26's
  M5 (S39, after Apr 20): no `tax_account_mapping` proposal adapter yet, so an approval has nothing
  to apply until then.
- The published key set comes from the caller until T-05-T21's C21 `tax_form_lines` sets are
  published; real-model runs and clearance are T-05-T47's (evaluation account).
- The suite's CPA labels stay `pending_cpa` (S37).

## Progress log
- `2026-11-12` — Built (S38). 12 unit tests pass; lint and types clean.
