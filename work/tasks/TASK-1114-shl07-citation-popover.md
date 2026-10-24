---
id: TASK-1114
title: SHL-07 CitationPopover container — single (a), stack with stepper, ghost edges and page thumb (b), methodology guidance 420 (c), hover preview vs pinned (d), Source moved with Re-link (e); Citations (n) and Procedures (n) list popovers; quotes through AgentText (P-03-T11)
spec: SPEC-322
acceptance_criteria: [AC-6, AC-7, AC-8, AC-9, AC-10, AC-11, AC-12]
risk_zone: green
status: done
epic: P-03
plan_key: P-03-T11
branch: s7-p03-viewer
created: 2026-10-24
updated: 2026-10-24
---

## Objective
"Hover intent 150 ms previews at 95% opacity, click pins and keeps the ring, Escape closes and refocuses the cell, and an unverified citation never renders as fact" (P-03-T11).

## Plan
- `apps/web/src/screens/SHL-07/CitationPopoverContainer.tsx`: `CitedCell` (reads its anchor's stack with `listCitationsOptions`, 150 ms hover intent, click pins, Enter and Space pin, lit while it is the popover's origin) and `CitationPopoverContainer` (the E2 `AnchoredPopoverHost` at 372 or 420 with `CitationCard`: header with the "‹ n / N ›" stepper, body, page thumb, moved line and Re-link…, footer "N citations"); `CitationList.tsx` (the 420 list popovers for "Citations (n)" and "Procedures (n)").
- `artboard.tsx` (gallery only): the AUD-04 Service Organizations and AUD-05 Risk Assessment underlays; `copy.ts` verbatim from the handoff.
- Tests: `SHL-07.test.tsx` (each artboard; hover timing, pin, Escape and refocus; unverified; no Re-link without `citation.relink`).

## Progress log
- 2026-10-24: built on F-05-T41's E1 store and E2 host without changing L2 (the L2 `CitationPopover` card has a different footer and stepper grammar from SHL-07's, so the container renders its own card in the host's `render`). 10 tests pass.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-268 | See TASK-1113 | No |
