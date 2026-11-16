---
id: TASK-8313
title: "A-08-T23: Agent modes fieldwork_attribute, flux_explain and confirmation_reconcile on workpapers.section_drafter (red)"
spec: SPEC-657
acceptance_criteria: [AC-5, AC-6, AC-9]
risk_zone: red
status: in-review
branch: a08-t23-fieldwork-agent-modes
worktree: /Users/ayushkbhatia/Accrued/abacus-s47g04
created: 2026-11-16
updated: 2026-11-16
plan_key: A-08-T23
---

## Objective
Spec section: docs/specs/SPEC-657-a08-audit-fieldwork-depth.md §6.
Agent modes fieldwork_attribute, flux_explain and confirmation_reconcile on workpapers.section_drafter (red).

## Plan (red)
1. `agents/specs/workpapers.section_drafter.yaml` version 15 (one spec, no new spec): three modes with their own prompts, the task scope's reads (`sample_set.read`, `trial_balance.read`, `confirmation.read`, `analytics.read`), the four tools, `respondent_text` untrusted; `_specs.py` and `_eval_suites.py` regenerated.
2. C17 tools: `sampling/agent_tools.py` (`sampling.read_selected_entry`), `ledger/agent_tools.py` (`ledger.counterparty_activity`, compute), `assurance/agent_tools.py` (`assurance.propose_explanation`, `assurance.propose_reconciliation`: suggestions only, with `tool_targets`).
3. `assurance/fieldwork_modes.py`: the three mode mappings (code facts), each refusing 404 with `audits.fieldwork_agents` off; the `analytics_line` and `confirmation` suggestion targets.
4. Three prompts `workpapers.section_draft.{fieldwork_attribute,flux_explain,confirmation_reconcile}@v1`.
5. Tests: `tests/unit/assurance/test_a08t23_fieldwork_modes.py`.

## Progress log
- `2026-11-16` — Built in the S47 sequential stack (DEC-5310). The v1 spec codegen and C17's registry gate pass; the unit file ran green (2 tests). Partial: the suite's fieldwork case sets are A-08-T25's (the modes sit on the frozen section-drafter suite meanwhile); the AgentBlocks rendering of these modes' output stays the drafter's SectionDraft. Gates and
  tests run once at the S47 end pass (build first, test last).
