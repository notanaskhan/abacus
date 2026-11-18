---
id: TASK-8625
title: "T-06-T14: Migration 0966 tax_other_entities_preview"
spec: SPEC-702
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
branch: t06-t14-other-entities-migration
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-18
updated: 2026-11-18
plan_key: T-06-T14
---

## Objective
Spec section: docs/plan/epics/T-06.md §4.2 NNNN_tax_other_entities_preview. AAA, shareholder allocations, provisions, rate reconciliation, deferred items, functional expenses, public support, allocation runs, form page renders and form diagnostics with TRI tags and footing CHECKs.

## Plan (amber)
1. migrations/versions/0966_tax_other_entities_preview.py on 0965: ten tax tables on a return's work item, forced RLS; functional_expense_lines_crossfoot (program + M&G + fundraising = total); tax_provisions_total (current + deferred = total); UNIQUE (work_item, checkpoint, rule_key) on diagnostics and (work_item, checkpoint, template, page) on renders (renders deletable: derived).
2. tax/registry.py, entity_tri TRI rows.

## Progress log
- `2026-11-18` — Built in the S50 sequential stack (DEC-5625). Gates and tests run once at the S50 end pass (build first, test last).
