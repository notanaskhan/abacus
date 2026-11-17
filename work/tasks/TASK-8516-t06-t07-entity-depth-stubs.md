---
id: TASK-8516
title: "T-06-T07: Contract stubs for tax entity depth, other-entity workpapers and form pages v1"
spec: SPEC-702
acceptance_criteria: [AC-1, AC-16, AC-32]
risk_zone: amber
status: in-review
branch: t06-t07-entity-depth-stubs
worktree: /Users/ayushkbhatia/Accrued/abacus-s49
created: 2026-11-17
updated: 2026-11-17
plan_key: T-06-T07
---

## Objective
Spec section: docs/plan/epics/T-06.md §4.3. TRI-tagged models, 501 routes behind their flags, golden-figure fixtures, docs/contracts/{tax-entity-depth,other-entity-workpapers,form-pages}.md.

## Plan (amber)
1. `tax/entity_depth_contract.py`: 24 routes (fixed assets read/detail/create/propose change; M-3, M-1; basis; §754 raise and send; states, sourcing propose and undo, PTET; AAA, provision, explain, functional expenses, allocation run; form pages, fields, trace, diagnostics, K-1 previews, draft download). TaxDepth* model names; every figure TRI. T-05's /schedules/m2 left to its owner.
2. Fixtures `abacus_tools/synthetic/scenarios/brightwater_hale/entity_depth_slice.py`: 8825 by property, states and PTET, K-1 previews, partner basis (handoff figures).
3. Three contract docs; mounted in tax.api ROUTERS; make generate.

## Progress log
- `2026-11-17` — Built in the S49 sequential stack (DEC-5516). Ruff and pyright clean; generate clean. Page PNG route lands with the renderer (T-06-T44). Footing tests are T-06-T09. Gates and tests run once at the S49 end pass (build first, test last).
