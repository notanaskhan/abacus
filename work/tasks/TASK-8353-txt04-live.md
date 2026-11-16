---
id: TASK-8353
title: "T-07-T26: TXT-04 live: the estate workpapers on the API, routed under the return's Review"
spec: SPEC-656
acceptance_criteria: [AC-12, AC-13, AC-14]
risk_zone: amber
status: in-review
branch: txt04-live
worktree: /Users/ayushkbhatia/Accrued/abacus-s47g04
created: 2026-11-16
updated: 2026-11-16
plan_key: T-07-T26
---

## Objective
Spec section: SPEC-656 F12 to F14; handoff TXT-04. TXT-04 live: the estate workpapers on the API, routed under the return's Review.

## Plan (amber)
1. `screens/TXT-04/live.tsx`: Inventory, Deductions, Computation and Gift history on `GET /v1/tax/returns/{id}/estate/*`; figures through `count`, no dollar sign; the state card never shows a figure while pending.
2. `/tax-returns/$returnId/review/estate` behind `tax.estate_workpapers`; the manifest gives TXT-04 its path. The gallery keeps the fixture artboards.

## Progress log
- `2026-11-16` — Built in the S47 sequential stack. tsc, eslint and the route and TXT-04 tests (79) clean. Partial: the derivation popovers (f), the c1 Approve values (L4) and the shadow tie-out label, the SHL-14 appraisal request and the parity tier. Gates and
  tests run once at the S47 end pass (build first, test last).
