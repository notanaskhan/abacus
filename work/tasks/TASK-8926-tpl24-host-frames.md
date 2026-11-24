---
id: TASK-8926
title: "F-08-T19: Specimen host frames and TPL-24 states a-g"
spec: SPEC-000
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: green
status: in-review
branch: s53-f08t19
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-23
updated: 2026-11-23
plan_key: F-08-T19
---

## Objective
Row acceptance: "TPL-24a to g render with D14 =SUM(D12:D13) linked, tickmarks 2/1/0/3/0, exactly F12-F14 changed in d, and no host brand colours or Microsoft marks." Specimen host frames (Excel and Word drawn in greys, specimens entry only) and TPL-24 states a-g.

## Done
- packages/ui specimens/host-frames.tsx: HostWindow, ExcelGrid, WordPage (specimens entry only, greys only)
- add-in kit exports AddinCard and AddinKv
- apps/web gallery/specimens/TPL-24 (index, copy, tests) registered at /components/screens/TPL-24
- tests: tpl24.test.tsx (8: formula, link, footing, tickmarks, F12-F14, offline, Word incoming, signed out, no brand marks); addin kit tests green

## Progress log
- `2026-11-23` — Built; parity run in the end pass.
