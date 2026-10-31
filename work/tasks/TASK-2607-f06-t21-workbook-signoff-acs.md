---
id: TASK-2607
title: F-06-T21 independent AC tests for T6 and SignOffSlots
spec: SPEC-400
acceptance_criteria: [AC-26, AC-27, AC-28, AC-29, AC-30, AC-31, AC-32]
risk_zone: amber
status: in-review
epic: F-06
plan_key: F-06-T21
branch: s21-f06-t21
worktree: /Users/ayushkbhatia/Accrued/abacus-s21
created: 2026-10-31
updated: 2026-10-31
---

## Objective
ADR-078's independent suite for F-06-T18 to T20, from F-06 §3 F5 Stories 5.1 to 5.7 and the
public props (`templates/workbook/types.ts`, `signoff` exports): "Tests prove the table never
sums, SignOffSlots never signs, reduced motion removes the 45 ms stagger, and the calc tree is
operable by keyboard."

## Scope
**In**: `packages/ui/src/templates/workbook/__ac__/workbook.ac.test.tsx`,
`packages/ui/src/signoff/__ac__/signoff-slots.ac.test.tsx`,
`apps/web/e2e/specimens/f06-workbook.ac.spec.ts`; the defect found (DEC-1657).
**Out**: parity tiers (F-06-T22 lock).

## Plan
1. [x] Component suites (jsdom): a server total the rows disagree with prints verbatim in the
   statement grid and the calc tree; negatives in parentheses, zero "—", no "$"; a source scan
   for number parsing or reducing in WorkbookLayout and CalcTree; off 6,200 and the Issue 2
   callback; five variance states in words with icons; building reads Pending with no enabled
   sign-off and no figures; Sign off… only calls `onOpenSignOff`, never `fetch`; the agent is never
   offered a sign-off or a slot; chips P before R whatever the order received; the reviewed pill
   and the stale "!" with "Changed after sign-off"; the package exports nothing that signs; the
   calc tree's arrows, focus lighting the typed cell within 360 ms, Enter pinning past leaving
   the step, Escape clearing and returning focus; match ids only from the typed locator; the
   scroller a named focusable region; Open in Excel and Download only call back.
2. [x] Browser spec: reduced motion leaves `document.getAnimations().length === 0` on T6a/b and
   TPL-06a/c; the scroller moves by arrows; T6c and TPL-06d enable no sign-off; T6d chips; T6e
   tree by keyboard; axe on each.
3. [x] Fix what the suites found (DEC-1657). Rollback: revert the PR.

## Progress log
- `2026-10-31` — Suites written from the stories and props only. First run: one defect (a slot
  named for the agent drew a chip; Story 5.5 says the agent never has a slot), fixed in
  `SignOffSlots.tsx`; the other failures were the suite's own selectors (the statement table is a
  `grid`; the ✓ is an icon; chips sit with the viewer's sign-off action). 33 passed with the
  kit's own suites (56 with CalcTree's). Observation, not changed: Escape clears the match at once
  and refocuses the step, and that refocus re-lights it after E1's focus intent (F-05's MatchStore
  contract, F-05-T42 asserts the same instant). Browser spec runs at the end review.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-1657 | SignOffSlots drops a slot named for the agent | No |
