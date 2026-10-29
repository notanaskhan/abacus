---
id: TASK-2028
title: P-07-T63 Parity lock, axe sweep and revision checklists
spec: SPEC-321
acceptance_criteria: [AC-31]
risk_zone: green
status: in-progress
epic: P-07
plan_key: P-07-T63
branch: s15n-p07-t63
created: 2026-10-29
updated: 2026-10-29
---

## Objective
Lock the six P0 screens (CLI-01, CLI-02, CLI-04, ENG-01, ENG-02, ENG-03) at Tier C, Tier D
green, the revision bullets for CLI-02, CLI-07, ENG-02 and ENG-03 as named tests, deviations
recorded.

Acceptance (backlog row): "All six P0 screens are parity-locked at Tier C before Fri May 28,
2027."

## Done in this pass
- The revision bullets were already named tests ("(R2)" acceptance tests in CLI-02, CLI-07, ENG-02
  and ENG-03's suites, P-07-T55); nothing to add.
- The parity manifest had no entry for any of the six: 40 Tier C window entries added from the
  handoff screenshots (source, SHA-256, window crop).

## End review (this branch)
- Fetch baselines (`pnpm visual:baselines`), measure the 40 entries, lock those under Tier C's
  3%, record the rest as deviations in the manifest with their reason.
- Run the six screens' `e2e/screens/*.spec.ts` (axe) and the Tier D specs.

## Progress log
- 2026-10-29: entries added (S15 group B); measurement and locks at the end review.
