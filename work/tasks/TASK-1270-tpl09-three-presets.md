---
id: TASK-1270
title: TPL-09a to TPL-09g three-preset specimen (F-05-T57)
spec: SPEC-048
acceptance_criteria: [AC-3, AC-8]
risk_zone: green
status: done
epic: F-05
plan_key: F-05-T57
branch: s9b-kit-screens
created: 2026-10-26
updated: 2026-10-26
---

## Objective
"Counts tie (Feld 4 = 2/1/1, Copperleaf 7 = 2+5, Ridgeline 11 = 5+6) and the bank reconciliation
shows tie, not Reconciled." The T9 specimen (TASK-1228) deferred TPL-09 to this task.

## Scope
**In**
- `packages/ui/src/specimens/tpl09.tsx`, `tpl09-data.ts`: `tpl-09`, artboards `tpl-09a` to
  `tpl-09g` on the T9 `QueueDetailLayout`, word for word from the TPL-09 spec and the Wave 0
  Templates canvas (`TP9`): the Feld 1040 tree for Kevin Osei beside the draft Ridgeline K-1 (the
  TPL-03 viewer file, box 18A lit with the chip and worksheet line 2a) and the worksheet with the
  proposed 1,550; the Copperleaf close review for Priya Raman beside the ••4410 reconciliation
  (`tie`); the Ridgeline 1065 for Samuel Ito with What it blocks and the seven workbook cells;
  agent fixing, waiting on the client, resolved with Reopen, and the empty queue.
- Kit additions (backward compatible; T9's 11 tests still pass): `IssueGroup.sub`, empty counts,
  `IssueDetailView.facts`, `summary` and `entities`, bands only when they have content;
  `QueueDetailLayout` `detail.right`; `FieldItem.proposed` with `FieldBlock` `onAccept`/`onReject`.
- Seed figures: `COPPERLEAF_BANK_REC` (blueprint 01 §9, CLS-05) and four footings in `FOOTINGS`.
- `tpl03.tsx` exports `K1_VIEW`. Registry entry `tpl-09`; parity `tpl-09.a` to `.g` at Tier B
  with a deviation.

**Out**
- TAX-06, CLS-06, TXP-10 (the screens this specimen becomes); SHL-10, SHL-15, TXP-11 targets.

## Definition of done
- [x] 13 tests in `templates/tpl09.test.tsx` (acceptance, one per artboard, Accept/Reject,
  resolve with a note, fix run); T9, TPL-03 and field-row suites still pass
- [x] `apps/web/src/fixtures/specimen-figures.test.ts` foots the reconciliation
- [x] tsc, eslint, prettier for `packages/ui`; tsc for `apps/web`
- [ ] Playwright not run locally: v1.63 wants chromium 1243, only 1248 is cached

## Rollback
Revert the commit; no migrations, generated files or flags.

## Progress log
- 2026-10-26: built and tested. Decisions in `tokens/DECISIONS.md` (F-05-T57) and DEC-384.
