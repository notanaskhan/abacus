---
id: TASK-1227
title: TPL-03a to TPL-03e Feld 1040 review specimen (F-05-T54)
spec: SPEC-048
acceptance_criteria: [AC-3, AC-8]
risk_zone: green
status: done
epic: F-05
plan_key: F-05-T54
branch: s8b-admin-kit
created: 2026-10-25
updated: 2026-10-25
---

## Objective
"Box 5 lights Interest Income $4,600, the Review count moves from 37 to 36 on approve, and 307,900,
4,600, 1,550 and 150,000 foot in seed tests."

## Scope
**In**
- `packages/ui/src/specimens/tpl03.tsx`: `tpl-03`, artboards `tpl-03a` to `tpl-03e` (Samuel Ito,
  E0) on the T3 `EvidenceTriad`: the review tree word for word from the TPL-03 spec, the draft
  Ridgeline K-1 and the Halvard 1099 in the E5 viewer (regions at C4 locators, EIN and TIN masked),
  the Sch E - K-1 matrix and the Form 1040 leadsheet. Box 5 ↔ Interest Income, 1099-DIV 1a ↔ line
  3b and 1b ↔ 3a share match ids (INV-2). Approve moves Review 37 → 36 with the toast; Unapprove
  moves it back.
- `templates/evidence-triad.tsx`: `TriadDoc.info`, `checkable`, `flagsNote`; `TriadFooter`
  `onUnapprove` (tonal "Unapprove Document", a person only); `EvidenceTriad.views`.
- Seed figures (`specimens/seed-figures.ts`): `FELD_K1`, `FELD_HALVARD`, `FELD_1040_LINES`,
  `RIDGELINE_K1S`, `RIDGELINE_SCHEDULE_K`; footings for Item L (1,912,500), line 2b (6,910) and
  Schedule K boxes 2, 5, 18A, 19A. The app's seed test ties boxes 2, 5 and 18A to the trust seed's
  K-1 citations and box 2 per partner to Ridgeline's K-1 packages.
- Parity `tpl-03.a` to `.e` at Tier B with a deviation (synthetic page images); Tier D panes.

**Out**
- TAX-04 and TAX-05 (T-04); the Worksheets and 2-Year Comparison content (not drawn in TPL-03).

## Definition of done
- [x] 9 tests in `templates/tpl03.test.tsx`; T3's 9 still pass
- [x] `apps/web/src/fixtures/specimen-figures.test.ts` (footings and the K-1 tie)
- [x] tsc and eslint for `packages/ui`; tsc for `apps/web`

## Progress log
- 2026-10-25: built. Decisions in `tokens/DECISIONS.md` (F-05-T54).
