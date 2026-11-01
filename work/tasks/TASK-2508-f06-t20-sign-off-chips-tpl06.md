---
id: TASK-2508
title: F-06-T20 C-25 sign-off chips, TPL-06 a–e Ridgeline capital accounts specimen and T6d
spec: SPEC-400
acceptance_criteria: [AC-30, AC-33, AC-34]
risk_zone: amber
status: done
epic: F-06
plan_key: F-06-T20
branch: s20-f06-t20
created: 2026-10-30
updated: 2026-10-30
---

## Objective
Story 5.5: sign-off chips that hand off to SHL-12 and never sign, on T6d and TPL-06e; and the
TPL-06 a–e specimen on the F-06-T18 WorkbookLayout over the F-06-T02 Ridgeline seed.

Acceptance (backlog row): "Every row crossfoots and every column foots with transfers netting to
0, TPL-06b ties at 6,866,200, and a SignOffSlots click only calls onOpenSignOff."

## Plan (amber)
- `packages/ui/src/signoff/SignOffSlots.tsx` → `SignOffSlotChips` (DEC-1557: P-04-T40 already
  exports `SignOffSlots`, the ladder with the Sign off action): chips sorted by level (P before
  R), olive "✓ XX" pills as buttons calling only `onOpenSignOff(target, level)`, stale = struck
  initials + amber pill with icon, "!" and "Changed after sign-off", optional "Reviewed · XX"
  green-tint pill; no empty slot, no create path, no agent slot. Exported from `@abacus/ui`.
- `WorkbookLayout`: renders `workbook.signOffs` as chips beside "Sign off…" when the consumer
  passes `signOff`, `onOpenSignOff` and `copy.signOffChips` (optional `WorkbookCopy` key).
- `gallery/specimens/T6`: state d ("✓ OB", "✓ DR"); copy keys `signOffs`, `openSignOff`.
- `gallery/specimens/TPL-06/index.tsx`: a (as drafted, M-2 off 6,200 → Issue 2, tie-out to
  Schedule L with the difference and the cause row, transfers footnote), b (tax-exempt column,
  Ending (fixed), difference "—"), c (five 452 panes, Tax · Book with the bands), d (building), e
  (signed off). Registered `TPL-06`. Figures carried from `fixtures/seed/tax` (never summed).
- Docs: `docs/screens/T6.md` d built; `docs/screens/TPL-06.md` a–e built + deviations.
- Rollback: revert; the kit change is additive (optional props).

## Acceptance
| Check | Test |
|---|---|
| Chips P before R; click only hands off; stale words + icon; reviewed pill; no empty slot | `packages/ui/src/signoff/SignOffSlots.test.tsx` |
| Rows crossfoot, columns foot, transfers net 0 | `apps/web/src/gallery/specimens/TPL-06/TPL06.test.tsx` |
| b ties 6,866,200; a off 6,200 alone | same |
| c five 452 panes; e "Reviewed · SI" and the chip opens SHL-12 | same |

## Progress log
- 2026-10-30: built (tests first, run at the end review). DEC-1557.
