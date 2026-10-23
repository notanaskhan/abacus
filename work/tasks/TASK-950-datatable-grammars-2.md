---
id: TASK-950
title: DataTable grammars 2 — statement and evidence, VarianceCell with five states, TallyStrip, AccountTree (F-05-T43)
spec: SPEC-048
acceptance_criteria: [AC-3, AC-8]
risk_zone: green
status: done
epic: F-05
plan_key: F-05-T43
branch: f05-t43-grammars-contracts
created: 2026-10-23
updated: 2026-10-23
---

## Objective
"The statement grammar shows whole dollars without $ and a dash for zero, and every variance state
renders in words."

## Scope
**In**
- `packages/ui/src/data/`: the `evidence` grammar in `DataGrid` (th 28, td 29, 12px, "$" with
  cents, fixed layout, `ValueChip`) and `EvidenceTable` (block cards on a well, `card={false}`);
  the `variance` column type with `VarianceCell` (posted, exception, explained, within,
  unexplained, each in words), the amber note corner, and the auto action column (Explain…, the
  issue link); `TallyStrip` (value, registry tally pills, running, sign-off chips, link, 45ms
  stagger); `AccountTree` (sections, 37px rows, 12/30/48 indents, ← → ↑ ↓ Home End Enter).
- Specimens `c-01-evidence`, `c-01-variance`, `c-01-tally-strip`, `c-01-account-tree` on the
  seed's Northwind figures; `NORTHWIND_CHANGE` with its footing (14,228,500.00 + 2,632,500.00 =
  16,861,000.00) checked by the app's seed test.
- The two gallery tests that visit `/components` transform the lazy gallery chunk in a `beforeAll`
  first: the registry grew past the 1s `findBy` on a cold compile. No assertion changes.

**Out**
- The 288 Explain editor and the note popover (the screen's, spec 06), grid and leadsheet
  grammars and virtualisation (F-05-T52).

## Definition of done
- [x] 9 tests in `data/grammars-2.test.tsx` (plus the 12 F-05-T27 tests; the no-sum scan covers the
  new files)
- [x] axe, target size, keyboard and INV sweeps green over the gallery
- [x] lint, tsc, prettier for `packages/ui` and `apps/web`

## Progress log
- 2026-10-23: built. packages/ui 917 tests pass. apps/web: 1147 of 1148 pass; the one failure,
  `src/status/status.test.ts` "holds every row of the registry" (expects 68 objects, finds 71), is on
  origin/main already: the C4 stub (P-03-T02) added `citation`, `viewer` and `evidence_unlock` to the
  registry without updating that count. Left for its owner.
