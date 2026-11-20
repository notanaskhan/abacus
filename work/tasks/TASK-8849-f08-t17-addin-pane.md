---
id: TASK-8849
title: "F-08-T17: AddinPane and AddinChrome C-39"
spec: SPEC-000
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: amber
status: in-review
branch: s52-f08t17
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-20
updated: 2026-11-20
plan_key: F-08-T17
---

## Objective
T22a to T22g render at 350 px with one primary per card, Sign-off disabled offline, and 'Sign off again as <name>...' only opening the dialog.

## Done
- packages/ui/src/addin (AddinPane, AddinChrome, index) exported
- addin-pane.test.tsx (a–g, no Office.js)
- DEC-5846

## Progress log
- `2026-11-20` — Plan (amber): L2 kit; never signs (INV-1). vitest at the end pass.
