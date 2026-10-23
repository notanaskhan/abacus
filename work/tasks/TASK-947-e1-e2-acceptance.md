---
id: TASK-947
title: Independent AC tests for E1 MatchProvider and E2 anchored popover host (F-05-T42)
spec: SPEC-048
acceptance_criteria: [AC-3, AC-8]
risk_zone: amber
status: done
epic: F-05
plan_key: F-05-T42
branch: f05-t41-match-cite
created: 2026-10-23
updated: 2026-10-23
---

## Objective
"Fake-timer intents (120, 140, 150 ms), scope anchoring, Escape refocus and locator-only ids pass,
and only the two affected cells re-render."

## Plan (amber)
- Written from F-05 G1, the T41 and T42 acceptance lines and plan 04 §4.3 E1/E2, through the public
  `tracing/index.ts` exports only (ADR-078).
- `packages/ui/src/tracing/e1-e2-acceptance.test.tsx` (13): 119 vs 120 ms for rows, 149 vs 150 ms
  for markers, 139 vs 140 ms release, pins hold, one match per scope, the 360 ms light, anchoring
  in the origin's scope and to the marker when nothing is lit, Escape refocus with and without the
  popover, `@ts-expect-error` on a bare string id, model text naming a cell lights nothing, and a
  40-cell render count where only the two affected cells re-render.
- `apps/web/e2e/tracing.spec.ts` (3, chromium, over the C-07 wired specimen): the popover is 8px
  right of the lit cell and top-aligned, flips to 8px left at the right edge, and Escape closes it
  and refocuses the marker.
- Rollback: revert; tests only.

## Progress log
- 2026-10-23: 13 vitest and 3 Playwright tests green. Builder and tester are one session in the
  solo edition (AMENDMENT-solo); the tests use only the public surface and the plan's numbers.
