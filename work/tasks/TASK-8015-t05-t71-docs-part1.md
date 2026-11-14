---
id: TASK-8015
title: "T-05-T71 part 1: entity-return workbook runbook, workpapers formula and tax entity README sections, tax-engine skill"
spec: SPEC-651
acceptance_criteria: []
risk_zone: green
status: in-review
branch: t05-t71-docs-part1
worktree: /Users/ayushkbhatia/Accrued/abacus-s44
created: 2026-11-14
updated: 2026-11-14
plan_key: T-05-T71
---

## Objective
"A fresh session can run, debug and roll back an entity-return workbook from the runbook alone."

## Plan
1. [x] `docs/runbooks/entity-return-workbook.md`: run, stuck run, recompute storm, consent revoked mid-run (with RB-17), engine version out of date, roll back.
2. [x] `workpapers/README.md` E13 formula engine section; `tax/README.md` entity returns section.
3. [x] `.claude/skills/tax-engine/SKILL.md` (protected; notanaskhan approves at the batch).
4. [ ] Part 2 (waits on S43): the runbook's "CCH differences" section and the README's CCH bridge and reconciliation lines (T-05-T60, T61: #1954, #1957), the Ridgeline slice 2 (T-05-T62: #1960), and the screen contracts' Deviations (with T-05-T66's states).

## Progress log
- `2026-11-14` — Part 1 written from the modules' docstrings on main (workbook_service, entity_run_plan, run_steps, cell_edit, workbook_imports, workbook_fix, workbook_export, entity_tri, entity_guards, formula, dag).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
