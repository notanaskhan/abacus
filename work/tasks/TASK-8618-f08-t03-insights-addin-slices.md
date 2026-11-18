---
id: TASK-8618
title: "F-08-T03: Seed slices: Insights client responsiveness, Granite Peak AP leadsheet and Word incoming changes"
spec: SPEC-000
acceptance_criteria: [AC-1]
risk_zone: green
status: in-review
branch: f08-t03-insights-addin-slices
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-18
updated: 2026-11-18
plan_key: F-08-T03
---

## Objective
Spec section: docs/plan/epics/F-08.md §2 (TPL-23, TPL-24), G1. Typed slices with seed tests.

## Plan (green)
1. apps/web/src/fixtures/contracts/{insights,addin}.ts: draft types.
2. seed/insights-responsiveness-2026-10-01.ts: due 2,804/1,432/214, 362 open not due, ages, quarters, the five lowest clients (TPL-23 handoff).
3. seed/granite-peak-fy2026-ap-leadsheet.ts: rows 12–13, D14 link, tickmarks, two Word incoming changes (TPL-24 handoff).
4. seed/insights-addin.foot.test.ts: 4,450; 63.0%; 4.8%; 576; 214 by age; quarters; 22·31·36·48·57; 4,180,000 and 3,310,000; exactly two Word changes.

## Progress log
- `2026-11-18` — Built in the S50 sequential stack (DEC-5618). Not run: vitest at the end pass. Gates and tests run once at the S50 end pass (build first, test last).
