---
id: TASK-8807
title: "F-08-T12: Allowlist bundle: @dnd-kit and @tiptap; engine chunk budgets"
spec: SPEC-000
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: red
status: in-review
branch: s52-f08t12
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-20
updated: 2026-11-20
plan_key: F-08-T12
---

## Objective
One protected PR merged in the first batch after Oct 20, 2028 adds the rows, package.json and lockfile installed by hand, and bundle-budget enforces dnd 40 KB and editor 180 KB.

## Done
- dependency-allowlist.yaml rows for eight packages (DEC-16)
- installed with pnpm in packages/ui, lockfile updated
- vite code-splitting groups engine-dnd / engine-editor
- bundle-budget.mjs ENGINE_BUDGETS (40 KB / 180 KB) and its unit test

## Progress log
- `2026-11-20` — Plan (red, protected manifest): allowlist rows, install, chunk groups, budget lines and test; rollback revert (lockfile with it). Real build budget check runs at the end pass.
