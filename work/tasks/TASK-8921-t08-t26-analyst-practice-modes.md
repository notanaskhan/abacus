---
id: TASK-8921
title: "T-08-T26: tax.return_analyst modes two_year and planning_screen"
spec: SPEC-710
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: red
status: in-review
branch: s53-t08t26
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-23
updated: 2026-11-23
plan_key: T-08-T26
---

## Objective
Row: "tax.return_analyst modes two_year and planning_screen: prompts, C17 tools (compare_years by code, engine summary, planning candidate), cited explanations and rationale with numbers by reference, internal talking points, client draft only under ADR P-25, consent and boundary refusals, DF-04 states." Acceptance: "Every output is a suggestion with verified citations, an unconsented taxpayer is refused with consent_7216, and the fast eval subset passes in CI."

## Done
- tax/practice_modes.py: inputs, outputs, settle, render, two_year_explain (route), planning_narrate (screen's narrator), verified document_text citations, suggestions only, appliers, consent and DF-04 refusals
- prompts tax.return_analyst.two_year@v1, planning_screen@v1
- C17 reads tax.read_engine_summary, tax.read_planning_candidate; spec tools and task scope (codegen regenerated)
- TAX-10 two-year:explain route live
- tests/unit/tax/test_t08t26_practice_modes.py (10 pass, incl. the tax fast subset)
- DEC-5923

## Progress log
- `2026-11-23` — Built in full. Human remainder: the Bedrock clearance run for the modes (DEC-5901); eval cases are T-08-T29. Red: security review in the end pass.
