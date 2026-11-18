---
id: TASK-8613
title: "Q-05-T04: Brightwater Hale QM and records seed slice (typed, golden figures)"
spec: SPEC-711
acceptance_criteria: [AC-34]
risk_zone: amber
status: in-review
branch: q05-t04-quality-slice
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-18
updated: 2026-11-18
plan_key: Q-05-T04
---

## Objective
Spec section: docs/plan/epics/Q-05.md §5.3. The QM and records slice at its snapshots, typed by the Q-05 contracts, with every golden figure computed from counts.

## Plan (amber)
1. abacus_tools/synthetic/scenarios/brightwater_hale/quality_slice.py: five agents (412/318/880/1,260/540 outputs; 37/29/61/63/16 overrides) and Denver's subset; QM-F-04/F-05 above the 8% tolerance; accuracy 1,320 of 41,260; E0 tiles (2 of 24, 5, 6.0%, 96.8%, 2, 92 days); register 24/38/58; PI-01 (12,250) below 12,610 at 4.9% of 252,200; batch 2026-Q3 (1,204 documents, 31 clients, Grace Holloway Sep 8) and fil02e (1,201).
2. Contract modules exported from practice, assurance and evidence api.py for the slice (tooling reaches a module only through api).
3. tests/unit/synthetic/test_q05t04_quality_slice.py: the goldens.

## Progress log
- `2026-11-18` — Built in the S50 sequential stack (DEC-5613). Partial: the service-API load (make seed-demo through register import, inspections, consultations, cases and batches) follows each service task (S51–S53); the 2026-Q2 batch (948 documents, 26 clients), C-01..C-05 and PI-02 join with their services. Fixtures export (make fixtures) once screens consume them. Gates and tests run once at the S50 end pass (build first, test last).
