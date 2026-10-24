---
id: TASK-1033
title: TPL-02a to TPL-02e Northwind 401(k) cockpit specimen (F-05-T51)
spec: SPEC-048
acceptance_criteria: [AC-3, AC-8]
risk_zone: green
status: done
epic: F-05
plan_key: F-05-T51
branch: s7-f05-t50-t53-ui-kit
created: 2026-10-24
updated: 2026-10-24
---

## Objective
"Rail counts tie at 11 of 24 (3+4+3+1), the trial balance tie reads $16,812,400.00, and dock
content in a, c and d is masked until the P-04 and P-09 kits land."

## Scope
**In**
- `packages/ui/src/specimens/tpl02.tsx`: the `tpl-02` specimen, artboards `tpl-02a` to `tpl-02e`
  on the T2 RecordCockpit (default 9:41 AM, idle with Run, blocked focus on Materiality, failed
  Internal Control with Retry, the idle pill rail). The rail's "11 of 24 received" is counted from
  the canvas's rows (the seed's PBC list, `SourceDocGroup` and `SourceDocRow` from F-05-T50); the
  canvas searches, sorts Missing first / Received first, and opens a document in the dock's Viewer.
  The dock's run content (projection, thread) carries `data-parity-mask` in a, c and d.
- The trial balance tie ($16,812,400.00 = $16,500,000.00 + $312,400.00) from the seed's figures:
  `investmentsAtFairValue` and `participantNotes` join the fixture seed (the Harborline summary
  of net trust assets, documents.py) and the specimen footings.
- Parity entries `tpl-02.a` to `tpl-02.e` at Tier B with recorded deviations (the masked dock in
  a, c and d; the rail's links without the Overview band).

**Out**
- The C-12 run rows and the SHL-11 decision card (P-04, P-09); the TPL-02 lock (F-05-T60).

## Definition of done
- [x] 11 tests in `templates/tpl02.test.tsx`; the footing in the app's specimen-figures test
- [x] axe harness, INV sweep and white-label sweep over the gallery
- [x] lint, tsc, prettier for `packages/ui` and `apps/web`

## Progress log
- 2026-10-24: built. Decisions in `tokens/DECISIONS.md` (F-05-T51).
