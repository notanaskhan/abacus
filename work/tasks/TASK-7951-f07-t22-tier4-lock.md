---
id: TASK-7951
title: "F-07-T22: tier-4 lock (Tier D for T13, T14, T17; Tier B for TPL-13, TPL-14, TPL-17; axe, keyboard, reduced motion, forced colours)"
plan_key: F-07-T22
spec: SPEC-652 (F-07 §5.4)
acceptance_criteria: [AC]  # four specimens Tier B locked, templates pass Tier D, axe 0 serious/critical
risk_zone: green
status: in-review
branch: f07-t22-tier4-lock
worktree: /Users/ayushkbhatia/Accrued/abacus-s43
created: 2026-11-14
updated: 2026-11-14
---

## Objective
Lock tier 4. Finishes F-07-T16/T18's and T-05-T55's Tier D partials for GraphCanvas and
FormRenderer.

## Plan
- `docs/design/parity-manifest.json`: 19 Tier B entries, `locked` (TPL-13 a, a′, b–f; TPL-14 a–f;
  TPL-17 a–f with the page body `[data-form-face]` masked), each with the handoff PNG's sha256.
- `apps/web/e2e/visual/tier-d-tier4.spec.ts` (Tier D geometry), `apps/web/e2e/specimens/
  f07-tier4.spec.ts` (axe on every board and the open popover; MonthGrid, graph and thumbnails
  keyboard; forced colours; reduced motion via `test.use`).

## Partial
- TXP-07's gallery (T-05-T55) has no tier-4 specimen of its own in the gallery; its Tier D rides
  on T14's checks via TPL-14. The visual project runs at the end pass (Playwright, baselines
  fetched by `pnpm visual:baselines`).

## Progress log
- 2026-11-14: written, not run (S43 end pass).
