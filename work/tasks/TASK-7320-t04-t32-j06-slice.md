---
id: TASK-7320
title: "T-04-T32: Journey slice for the shadow flip: j06 6, 7, 8, 8b and 'j06 10 final approval blocked by Draft K-1'"
spec: SPEC-649
acceptance_criteria: [AC-13]
risk_zone: amber
status: in-progress
branch: s37-t04-t32
worktree: /Users/ayushkbhatia/Accrued/abacus-s37
created: 2026-11-12
updated: 2026-11-12
plan_key: T-04-T32
---

## Objective
The slice passes on staging three nights running with INV-1 to INV-5 asserted and axe clean, the
e2e precondition for the Tue Mar 28 flip.

## Built
- `apps/web/e2e/journeys/J06-1040-season.spec.ts (a new describe beside T-01-T29s)`: the five named tests on the review artboards
  in fixture mode (axe and INV-1 to INV-5 through the harness, plus no "I approved"/"I changed"
  text); full stack and staging are fixme until T-04-T29's live hosts and staging.
- Gallery: TAX-04, TAX-05, TAX-06, TAX-07 and TXI-01 registered (`screens/gallery.tsx`).

## Partial (status in-progress)
- Three staging nights with the fake CCH and fake Textract: staging is not up, and the steps'
  live hosts are T-04-T29's remaining screen work.

## Progress log
- `2026-11-12` — Fixture slice built (S37); runs at the end pass.
