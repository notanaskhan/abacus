---
id: TASK-8635
title: "T-06-T22: Brightwater Hale Ridgeline depth slice (register, basis, states and PTET, DF-34 badge)"
spec: SPEC-702
acceptance_criteria: [AC-19]
risk_zone: green
status: in-review
branch: t06-t22-ridgeline-depth
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-18
updated: 2026-11-18
plan_key: T-06-T22
---

## Objective
Ridgeline's 2025 Form 1065 at E0 (Mon Sep 14, 2026, 9:24 AM CT) for TXP-03, TXP-08, TXP-09 and TXP-10: the fixed-asset register with the Elm Street roof flag and the Larimer Feb 3, 2025 binding contract, land by site, basis by partner with Pell Street II's 28,595, apportionment and PTET paid Mar 12, 2026 with the NY gap variant, and the DF-34 badge 11, 10, 9.

## Plan (green)
1. abacus_tools/synthetic/scenarios/brightwater_hale/ridgeline_depth_slice.py: handoff rows as typed constants; totals, shares, PTET, basis differences and the badge computed by code (ADR-050).
2. tests/unit/synthetic/test_t06t22_ridgeline_depth.py: cost 15,752,000; accumulated 2,625,167; 8825 by property 169,500 / 360,000 / 204,000; land 3,600,000; Larimer check to tie on Feb 3, 2025; 4 of 5 partners reconcile, Pell Street II off 28,595; 46.0 / 31.5 / 22.5; PTET 64,096 and credits foot; NY gap PAID 2 of 3; badge 11, 10, 9.
3. Rollback: revert; the slice is data only.

## Progress log
- `2026-11-18` — Built in the S50 completion round (DEC-5635). Partial: the service-API load under kernel.clock (register rows through tax.api fixed assets, PTET payments, nexus facts, the §754 context and the citation regions on the Larimer invoice) waits on the T-06 service tasks that own those writes (T-06-T10 register service is the only one on main; the states, basis and nexus services land with T-06-T29 onward). The 03 Liabilities sheet and the TAX-11 page facts are not in this slice. Open question: TXP-03 c (Larimer check ties at 10:12) does not say whether the Larimer review point resolves; DF-34 counts only TXP-10 d and TXP-09 e, so the slice moves the badge on those two only. Gates and tests run once at the S50 end pass (build first, test last).
