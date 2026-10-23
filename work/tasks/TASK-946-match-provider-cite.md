---
id: TASK-946
title: E1 MatchProvider, E2 anchored popover host, C-07 CiteMarker and CitationChip visuals (F-05-T41)
spec: SPEC-048
acceptance_criteria: [AC-3, AC-8]
risk_zone: amber
status: done
epic: F-05
plan_key: F-05-T41
branch: f05-t41-match-cite
created: 2026-10-23
updated: 2026-10-23
---

## Objective
"One match per scope lights every data-match element over 360 ms, and match ids come only from
typed citation locators, never model text (INV-2)."

## Plan (amber)
- **Files.** New `packages/ui/src/tracing/` (amber zone, INV-2): `types.ts` (C4 `Locator` union,
  branded `MatchId`, `CitationView`), `match-store.ts` (`createMatchStore`, `matchIdOf`,
  `contractMatchId`, the timing constants), `match.tsx` (`MatchScope`, `useMatch`, `Matchable`,
  the light classes), `popover-host.tsx` (`AnchoredPopoverHost` on Radix Popover with a virtual
  anchor), `cite.tsx` (`CiteMarker`, `CitationPopover`, `CitationPopoverHost`, `CitationChip`,
  `CitationFooter`). `motion.css` gains `motion-cite-in`; `HIT.marker` gives the 17px marker its
  24px target. The legacy numbered chip is renamed `NumberedCitation` (two legacy screens).
- **Contract.** C4 (`docs/contracts/c04-citations-viewer.md` §3.1): the client derives the same ids
  the server does, and otherwise takes `match_id` off a typed citation or region; it never sends one.
- **Tests.** Builder tests in `tracing/tracing.test.tsx`; the independent ACs are TASK-947.
- **Migrations, flags, registry.** None.
- **Rollback.** Revert the commit; no screen consumes the engine yet.

## Scope
**Out**
- The CitationDialog (1140) and CitationPopover data paths: P-03 (SHL-07). The SourceViewer's
  RegionLayer: F-05-T47. Prose parsing of `[n]` markers out of agent text: not built (a marker is
  placed from a citation list, never from text).

## Definition of done
- [x] 10 builder tests (`tracing.test.tsx`); specimens `c-07-cite-marker`, `c-07-citation-popover`,
  `c-07-citation-chip`, `c-07-wired`, `e1-match-light`
- [x] axe (every specimen, overlays, forced colours, target size), INV sweep green over the gallery
- [x] lint, tsc, prettier for `packages/ui` and `apps/web`; legacy Board and spec021 tests green

## Progress log
- 2026-10-23: built. packages/ui vitest 906 passed; e2e a11y, inv and tracing specs green against
  the gallery. The first target-size run flagged two adjacent 17px markers; fixed with `HIT.marker`
  and a word between them in the specimen. Parity: no manifest entry yet. C-07 has no screen artboard;
  its kit-sheet crops (kit-handoffs C-07 screenshots 02 to 05) are to be pinned at Tier A with the
  M5 lock (F-05-T49). Tier D-style placement is asserted in `e2e/tracing.spec.ts`.
