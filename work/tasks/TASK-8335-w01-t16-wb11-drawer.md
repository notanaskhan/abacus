---
id: TASK-8335
title: "W-01-T16: WB-11 drawer in fixture mode"
spec: SPEC-659
acceptance_criteria: [AC-20, AC-23, AC-24, AC-25, AC-26]
risk_zone: green
status: in-review
branch: w01-t16-wb11-drawer
worktree: /Users/ayushkbhatia/Accrued/abacus-s47g04
created: 2026-11-16
updated: 2026-11-16
plan_key: W-01-T16
---

## Objective
Spec section: handoff WB-11.
WB-11 drawer in fixture mode.

## Plan (green)
1. `apps/web/src/screens/WB-11/`: `IntegrationDrawer` on the design system's O2 Drawer (480): a connected, c needs reauth, d client ledger (Copperleaf and Ridgeline client-connected, no firm-side connect), f non-admin; also b consent and e the typed-name disconnect confirm (W-01-T17's); tests.
2. Registered in the gallery; `routes/manifest/wb.ts` marks WB-11 `fixture`.

## Progress log
- `2026-11-16` — Built in the S47 sequential stack. tsc, eslint and the screen tests (8) clean while building. Partial: the `?ov=connection:<key>` overlay registration on firm routes, the file-bridge state, planned links on every row and the live read through W-01-T15's detail route. Gates and
  tests run once at the S47 end pass (build first, test last).
