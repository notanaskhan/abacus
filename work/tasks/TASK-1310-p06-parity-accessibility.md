---
id: TASK-1310
title: P-06 parity and accessibility - 23 artboards at Tier C, BND-01/02 locks, Tier D hosts, keyboard suites (P-06-T26)
spec: SPEC-319
acceptance_criteria: [AC-29, AC-30]
risk_zone: green
status: in-review
epic: P-06
plan_key: P-06-T26
branch: s10-p06-closeout
created: 2026-10-26
updated: 2026-10-26
---

## Objective
P-06-T26: "Parity and accessibility: 23 artboards reported at Tier C, BND-01 and BND-02 locked at Tier C, Tier D on host templates, keyboard suites". Acceptance: "The parity report is published and axe shows zero serious or critical findings." Targets: P-06 §5.5, §5.6; DoD items 2 and 3.

## Plan
- **Limits of this session:** no Playwright (the cached chromium does not match), no Docker, no backend tests. Parity diffs, the Tier C locks, Tier D and axe cannot be measured here; nothing is claimed for them.
- **Parity report:** `docs/quality/parity-P-06.md`: each of the 23 built artboards (from the four screen contracts) with its tier target and status, the reason it was not run, the BND-01/BND-02 locks recorded as pending measurement, Tier D per host, SHL-14 c deferred to A-03.
- **Contracts:** each `docs/screens/<ID>.md` Parity table says "not run" with the reason; no row uses the word `screen-rows.ts` parses as a lock until a run measures it.
- **axe:** stays in Playwright (`@axe-core/playwright`, the allowlisted package). Add the missing artboards: BND-01 b, BND-02 g, and a new `e2e/screens/SHL-20.spec.ts` for a–f (with the overlay b and f open).
- **Keyboard (vitest):** a suite per screen, `src/screens/<ID>/<ID>.keyboard.test.tsx`, on the fixture scenarios: tab order to the primary actions (read from the DOM: `src/testing/keyboard.ts`, since jsdom does not move focus on Tab), Escape closes each overlay, focus returns to its opener; plus §5.6's specifics (tiles `aria-pressed`, Eye toggle, dirty guard, tablist arrows, linked validation error, card `aria-busy`, feedback radio group).
- **A defect found** gets fixed with its test and an ED row (ED-090 is the only number available).
- **Checks:** the four screens' vitest files plus `screen-parity.test.ts`; eslint and prettier on touched TS; `tsc` for apps/web.
- **Rollback:** revert the commit; the SHL-20 fix is one component.

## Progress log
- 2026-10-26: planned and built on `s10-p06-closeout`.
- 2026-10-26: keyboard suites written: BND-01 (6), BND-02 (9), SHL-14 (6), SHL-20 (6). `pnpm -C apps/web exec vitest run src/screens/BND-01 src/screens/BND-02 src/screens/SHL-14 src/screens/SHL-20 src/routes/screen-parity.test.ts`: 9 files, 124 tests passed (97 existing + 27 new).
- 2026-10-26: **ED-090.** SHL-20's card ignored Escape and ✕ left focus on the page. Fixed in `src/screens/SHL-20/index.tsx`: Escape from anywhere in the frame closes the card and focus returns to the chip; portalled overlays (ReturnDialog, "Why?", O3 sheet) keep their own Escape (checked by the suite). The test failed before the fix (3 of 6 red, one of them a test bug in reading radio names, fixed) and passes after.
- 2026-10-26: **Not met, carried (DEC-408):** T1 `IndexList` rows are not keyboard-selectable (§5.6 "Space selects, Enter opens"); a T1 kit change, not a screen's. The Eye's "Internal only" helper is not linked by `aria-describedby`. No test was written to fail for these; they are listed in the report §4.
- 2026-10-26: axe specs: `BND-01.spec.ts` + b, `BND-02.spec.ts` + g, new `SHL-20.spec.ts`. Not run.
- 2026-10-26: parity report written; contracts' Parity tables updated (BND-01's old note "locked (blocking) at the end of S10" parsed as a lock; reworded). `screen-parity.test.ts` green.
- 2026-10-26: `tsc --noEmit` for apps/web: no error in any file this task touched; it reports 12 errors in the generated `packages/api-client/src/{client,core}/*.gen.ts` (exactOptionalPropertyTypes), which this task did not touch. eslint and prettier clean on the touched TS.
- **Left for the batch merge:** pin the crops in `parity-manifest.json`, fetch baselines, run the four axe specs and `pnpm parity:screens`, record the numbers in the report, flip BND-02 to `fixture`, then lock BND-01 and BND-02 at Tier C and decide the harness rule for a locked Tier C. Status stays `in-review` until axe is run: the acceptance's "axe shows zero serious or critical findings" is not yet shown.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-408 | What the report claims (nothing unmeasured), why the locks are pending, axe in Playwright only, keyboard suites in vitest, the T1 keyboard gap carried to the kit | No |
