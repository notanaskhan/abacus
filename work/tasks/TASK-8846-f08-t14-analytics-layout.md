---
id: TASK-8846
title: "F-08-T14: AnalyticsLayout T21"
spec: SPEC-000
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: amber
status: in-review
branch: s52-f08t14
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-20
updated: 2026-11-20
plan_key: F-08-T14
---

## Objective
T21a to T21g render, a narrowed chip turns amber and every footer names the scope, T21e is a designed flag-off state and T21f shows counts with names locked.

## Done
- packages/ui/src/templates/analytics-layout.tsx + exports
- analytics-layout.test.tsx
- gallery T21 board a–g
- DEC-5845

## Progress log
- `2026-11-20` — Plan (amber): L1 template; restricted mode never links (INV-3). vitest at the end pass.
