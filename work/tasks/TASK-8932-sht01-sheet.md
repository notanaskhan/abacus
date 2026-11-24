---
id: TASK-8932
title: "K-03-T16: SHT-01 on SheetLayout cockpit at /audits/$auditId/sheets/$sheetId; states b, c, a without agent cells, f locked; Sign-offs opens SHL-12"
spec: SPEC-000
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: green
status: in-review
branch: s53-k03t16
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-23
updated: 2026-11-23
plan_key: K-03-T16
---

## Objective
Row acceptance: "SHT-01b, c, a and f render in fixture mode at their clocks with no column letters, row numbers or zebra rows, locked cells refuse edits with the final tooltip, and Sign-offs opens ?ov=signoff for the selected rows."

## Done
- screens/SHT-01 (index, copy, scenarios, tests); route behind sheets.enabled; manifest path (status planned until SHL-14 sheet origin)
- domain/sheets public entry
- tests: SHT-01.test.tsx (5)

## Progress log
- `2026-11-23` — Built; flips to fixture/live with K-03's request-from-rows row (link contract).
