---
id: TASK-9006
title: "T-08-T33: Red paths for amendments"
spec: SPEC-000
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: red
status: in-review
branch: s54-t08-t30-amendments
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-26
updated: 2026-11-26
plan_key: T-08-T33
---

## Objective
Only Neil Ashcroft can approve the Okafor amendment or decide the Vantage election, both human-only through all five layers.

## Done
- tax/amendment_gates.py: approval blockers for amended returns and AARs (with words), the amendment_approval gate kind, the bba_election decision kind reserved to the signer (code's options from the engine's imputed underpayment and the adjustments; applier writes aar_elections)
- amendments: the approval-requested event classified
- tests: 2 integration (only Neil approves; Yusuf and an agent refused; Part II blocker; routing notifies Neil only; only Neil decides the election, agent and staff refused, the row is human)
- the Okafor fixture moved to tests/integration/backfill/okafor_amendment.py
- DEC-6012

## Progress log
- `2026-11-26` — Built; T30 + T33 suites green. Security review of this red diff in the end pass.
