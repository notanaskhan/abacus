---
id: TASK-6719
title: "T-04-T22: TXI-01 worksheet editor states a-g in fixture mode, panes 300-566-490"
spec: SPEC-649
acceptance_criteria: [AC-3]
risk_zone: green
status: in-review
branch: s35-t04-t22
worktree: /Users/ayushkbhatia/Accrued/abacus-s35
created: 2026-11-10
updated: 2026-11-10
plan_key: T-04-T22
---

## Objective
TXI-01a-g render from scenarios, line 20 lights Box 18A on page 3, the IT-201 figures tie to 615,605, 52,805, 51,536 and 1,269, and no edit saves without a reason.

## Plan
`apps/web/src/screens/TXI-01/` (new): `copy.ts` (the IT-201 sections and fields, W-2 boxes, tree,
copy verbatim), `Editor.tsx` (`WorksheetEditor` on 300 · 566 · 490: tree with TSJ tags, green "+"
and amber pencil; 42-high field rows, 96-wide values, provenance line, amber updated pill over
the struck prior, sign-off chips, flags; line 20 ↔ Box 18A lighting; Edit with a required reason;
b provenance popover, c W-2, d flagged, e new-this-year IT-653, f signed-off section, g engine
recomputed NYC rows and IT-360.1), `TXI-01.test.tsx`. `docs/screens/TXI-01.md` status fixture.

## Partial
- The save, SHL-12, SHL-15 and TAX-06 are the host's (callbacks); live wiring with the TAX-04 host.

## Progress log
- `2026-11-10` — Built; tests written, not run (end pass).
