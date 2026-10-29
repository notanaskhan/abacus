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
- 2026-10-29 (end review): baselines cropped from the handoff (version 2026-10-21) and the 39
  window entries measured at 1440 x 900, 2x (`parity.spec.ts`, visual project). Diff %:
  CLI-01 a 3.30 · b 1.90 · c 3.22 · d 0.57 · e 0.50 · f 0.81;
  CLI-02 a 3.31 · a2 3.33 · b 2.04 · c 1.63 · e 1.63 · f 1.93;
  CLI-04 a 2.07 · b 5.03 · c 2.72 · d 2.11 · e 5.01 · f 3.84 · g 0.95;
  ENG-01 a 3.87 · b 1.97 · c 1.23 · d 1.09 · e 0.82;
  ENG-02 a 2.59 · b 1.61 · c 1.16 · d 1.03 · e 0.85 · f 4.03 · g 1.15.
  22 under 3 %, 9 between 3 and 5.1 %, none above. Fixes: `cli-02d.window` removed (P-07-T19
  built CLI-02 a, a2, b, c, e, f; there is no d artboard, so the entry timed out); ENG-03's
  selectors are the artboard itself (the wizard is a dialog portalled out of it, with no app
  shell), and its eight entries carry a deviation: the artboard draws the wizard on the bare
  1440 x 900 stage, so the 1400 x 860 window crop cannot be compared until it draws the shell.
  Not done: locks (Ayush chose the short check without locks; Tier C stays report-only either
  way), so the row's acceptance ("parity-locked at Tier C") stays open; ENG-03's shell for
  measurement. Screen specs (axe) for the six: 57 of 59 pass; CLI-04 b and e fail on duplicate
  text locators, already on main.
- 2026-10-29: Ayush chose to lock: the 22 entries under 3 % are `locked` (DEC-1064). The nine
  between 3 and 5.03 % stay report-only and ENG-03 keeps its deviation, so the acceptance
  (all six locked) stays open on those.
