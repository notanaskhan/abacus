---
id: TASK-6613
title: "A-07-T39: AUD-25 Assembly & archive in fixture mode on T2"
spec: SPEC-644
acceptance_criteria: [AC-39]
risk_zone: green
status: in-review
branch: s34-a07-t39
worktree: /Users/ayushkbhatia/Accrued/abacus-s34
created: 2026-11-10
updated: 2026-11-10
plan_key: A-07-T39
---

## Objective
All six AUD-25 artboards render from fixtures and no delete control exists anywhere in states c
and d.

## Plan
1. `screens/AUD-25/copy.ts`: the handoff spec's and revision R2's words verbatim.
2. `screens/AUD-25/Archive.tsx`: the clock card (3 px progress; red tint only at 7 days or fewer),
   the nine-item checklist (read-only once locked), the binder index table, Request lock… /
   Lock archive… (manager or partner), the lock sheet with "Assembly is complete" and R2's
   "Then roll forward to PY2026 (ENG-13)", Locked · sealed with the seal and G9, the post-lock
   addition row and "+ Add after lock…", R2's Archive and roll forward… / Roll forward…, the Agent
   dock narration through `AgentText`.
3. `AUD-25.test.tsx`: every state, no delete control in c and d, the lock sheet, the red tint.

## Progress log
- `2026-11-10` — Built; prettier, tsc, eslint clean. Tests not run (end pass). Partial: fixture
  mode only (no route mounts it; the live read of `GET …/archive`, the lock route and the
  step-up arrive with the screen's live row); the addition sheet's reason and approver fields are
  A-07-T42's.
