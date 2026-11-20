---
id: TASK-8829
title: "T-06-T38: ledger.tb_mapper mode tax_lines"
spec: SPEC-702
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: red
status: in-review
branch: s52-t06t38
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-20
updated: 2026-11-20
plan_key: T-06-T38
---

## Objective
No balance reaches the model context, and without the target's consent the preview shows 7 blank accounts and makes zero gateway calls.

## Done
- tax/tb_mapper_tax_lines.py (consent first, names and numbers only, evidence-checked codes, judgment blanks with explanations)
- tax/tb_mapper_tools.py propose tool tax.suggest_tax_lines (C17 suggestions, target tb_handoff_tax_line)
- prompts ledger.tb_mapper.tax_lines@v1 and tool.tax.suggest_tax_lines@v1
- spec yaml tools + tri, _specs_v2 regenerated
- tests/unit/tax/test_t06t38_tb_mapper_tax_lines.py
- DEC-5831

## Progress log
- `2026-11-20` — Plan (red): mode module, tool, prompts, spec codegen, unit tests; rollback = revert (no migration). The preview route wiring that calls the mode lands with T-06-T39. Tests at the end pass.
