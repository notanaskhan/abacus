---
id: TASK-8412
title: "A-09-T29: Capability ledger.tb_mapper"
spec: SPEC-658
acceptance_criteria: [AC-1]
risk_zone: red
status: in-review
branch: a09-t29-tb-mapper
worktree: /Users/ayushkbhatia/Accrued/abacus-s48
created: 2026-11-17
updated: 2026-11-17
plan_key: A-09-T29
---

## Objective
Spec section: docs/plan/epics/A-09.md §6. Capability ledger.tb_mapper: spec YAML (propose only), registered prompt v1 and output schema (catalogue id, confidence word, reasoning up to 140 characters), data-boundary context builder (code, name, entity, computed facts), the mapping run with suggestions, adopt route, Request changes rerun, group confirm across entity sets.

## Plan (red)
1. `agents/specs/v2/ledger.tb_mapper.yaml` (workflow shape, one model call, propose tool `assurance.suggest_account_mappings`, task scope `mapping_set.read` + `suggestion.create`, untrusted `account_names`, `client_data: none`, suite `evals/tb_mapping`); `_specs_v2.py` and `_eval_suites.py` regenerated; prompts `ledger.tb_mapper@v1` and the tool's description.
2. `assurance/tb_mapper.py`: `TbMapperInput`/`TbMapperOutput`, amounts redacted from names, code's facts (balance side, last year's line), `settle` (catalogue lines only, confidence word, reasoning <= 140), `run_suggestions` (a person's inline capability run through `agents.start_capability_run`/`end_capability_run`, synthetic firms only).
3. `assurance/agent_tools.py`: `assurance.suggest_account_mappings` (suggestions on target `account_mapping`, with `tool_targets`); `fieldwork_modes.register` adds the target. Routes `POST /v1/mapping-sets/{id}/suggestions` (`?rerun=true` = Request changes) and `POST /v1/mapping-sets/group-confirm` (each set's own confirm, a live person). Adopt is AUD-31's existing account edit by a person.
4. Tests: `tests/unit/assurance/test_a09t29_tb_mapper.py`.

## Progress log
- `2026-11-17` — Built in the S48 sequential stack (DEC-5409). Lint and pyright clean; specs and eval-suite registry regenerated; the app imports. Partial: no `TbMappingWorkflow` exists on main (A-03's rules run synchronously in `mapping_live.run_start`), so there is no workflow to patch as `tb_mapper_suggestions` and no replay history to keep; the suggestions run is a separate inline capability run after the rules. The AUD-31 suggestion chips and adopt-from-suggestion button are FE work outside this row. Gates and tests run once at the S48 end pass (build first, test last).
