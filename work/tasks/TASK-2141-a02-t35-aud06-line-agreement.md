---
id: TASK-2141
title: A-02-T35 AUD-06 line agreement and edit with reason on P-04 fields
spec: SPEC-000  # A-02-T35 row; A-02 §3.6 AC-6.1, AC-6.2, AC-6.4 are the spec
acceptance_criteria: [AC-1]  # the backlog row's acceptance; A-02 §3.6 AC-6.1, AC-6.2, AC-6.4 in the body
risk_zone: green
status: in-review
epic: A-02
plan_key: A-02-T35
branch: s16-a02-t35
created: 2026-10-30
updated: 2026-10-30
---

## Objective
Acceptance (backlog row): "Marcus Delaney agrees KRS Target 2045 to Harborline p.1 and the chip
popover names him and the page, while amount cells offer no edit."

## Plan
- `screens/AUD-06/LineActions.tsx` (lazy, like TbLive): a row menu where the view grants
  `trial_balance.annotate`: Agree to source… (viewer search over the dock's open document, pick a
  page, then `POST …/references` and an L1 `POST …/ticks` on `wp_ref:<account>`), Mark reviewed
  (L2) when P-04 allows `field.sign_off`, Edit… (WP ref and area with one required reason through
  `PUT …/value`). No amount control anywhere.
- `TrialBalanceOptions.sourceVersionId` (the host's viewer document), falling back to the
  selected line's linked citation.
- Fixtures: P-04 field routes in `tbHandlers`.
- Test: `screens/AUD-06/LineActions.test.tsx`.

## Progress log
- 2026-10-30: built; tsc and eslint clean. Tests run at the end review. The acceptance names
  "p.1"; the Harborline fixture's fund rows sit on page 2, so the test agrees to page 2.
