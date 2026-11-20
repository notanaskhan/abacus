---
id: TASK-8853
title: "K-03-T09: Sheets contract stub (SH-1)"
spec: SPEC-721
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: amber
status: in-review
branch: s52-k03t09
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-20
updated: 2026-11-20
plan_key: K-03-T09
---

## Objective
Every SH-1 route answers 501 under its one matrix action, the shapes match F-08's SheetVM type (F-08 §4 view-model table, built with SheetLayout in F-08-T08), and fixture mode serves every SHT-01, SHT-02 and SHT-04 artboard.

## Done
- workpapers/sheets_contract.py + router
- SheetVM in packages/ui sheet/types.ts
- apps/web domain/sheets/vm.ts toSheetVM
- make generate
- fixtures/seed/sheets-sh1.ts + foot test
- scenarios SHT-01, SHT-02, SHT-04
- docs/contracts/sheets.md
- DEC-5850

## Progress log
- `2026-11-20` — Plan (amber): contract-first stub; rollback = revert. Consumer tests are K-03-T10.
