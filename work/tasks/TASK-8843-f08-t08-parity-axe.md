---
id: TASK-8843
title: "F-08-T08: T18 parity and axe carry"
spec: SPEC-660
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: green
status: in-review
branch: s52-f08t08
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-20
updated: 2026-11-20
plan_key: F-08-T08
---

## Objective
T18a to T18i render from typed view models, a P or R slot click calls onOpenSignOff and never signs, and T18b scrolls with select and Key frozen.

## Done
- gallery/specimens/T18 board a–i (handoff placeholder content) registered for /components/screens/T18
- e2e/specimens/f08-t18.spec.ts (axe per state, parity screenshots under ABACUS_VISUAL, P·R slot, T18b scroll)

## Progress log
- `2026-11-20` — Carry from S51 TASK-8747 (the handoff was at sources/handoff/.../T18 Sheet). Baselines are written by the first ABACUS_VISUAL run in the end pass.
