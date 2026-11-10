---
id: TASK-6714
title: "A-07-T48: parity, accessibility and keyboard for the A-07 artboards: Tier C report and locks, Tier D on T2 and T10 geometry, axe AA, focus order through every O3 sheet"
spec: SPEC-644
acceptance_criteria: [AC-37]
risk_zone: green
status: in-review
branch: s35-a07-t48
worktree: /Users/ayushkbhatia/Accrued/abacus-s35
created: 2026-11-10
updated: 2026-11-10
plan_key: A-07-T48
---

## Objective
All locked artboards pass Tier C with the DF-11 and DF-20 copy deviations masked and recorded, and axe reports zero violations.

## Plan
1. Gallery: AUD-22, AUD-23, AUD-24 and AUD-25 registered (`screens/gallery.tsx`), each artboard in the
   app shell (`[data-artboard] [data-shell=app]`), the fixture frames as the screens' own tests use.
2. `docs/design/parity-manifest.json`: Tier C `.window` entries, **locked**, for AUD-22 a/b/c,
   AUD-23 a/b, AUD-24 a/b/d/e and AUD-25 a/b/c (12 of the 25 locks), sources pinned by SHA-256,
   spinners and presence masked.
3. `e2e/screens/AUD-a07-a11y.spec.ts`: axe (serious/critical blocking) on every frame; Tab never
   stuck; each O3 sheet traps focus, Escape closes it, focus returns to its opener.
4. `e2e/visual/tier-d-a07.spec.ts`: T2 (330 · 696 · 330) on AUD-24/25, T10 (470 · 896) on AUD-22/23.

## Partial
- AUD-18, AUD-19 and AUD-21 (13 of the 25 locks) are data-driven canvases without a gallery
  registration yet; their locks wait for an artboard host (their screen tests stay the check).
- DF-11/DF-20 copy masks: none needed on the four registered screens' locked frames; recorded
  here. The visual and axe runs need Playwright browsers: CI's gallery job.

## Progress log
- `2026-11-10` — Built; specs written, run in CI's visual project at the end.
