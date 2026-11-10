---
id: TASK-6624
title: "A-01-T33: AUD-02 and AUD-03 parity carry-over (DEC-909)"
spec: SPEC-330
acceptance_criteria: [AC-1]
risk_zone: green
status: in-review
branch: s34-a01-t33
worktree: /Users/ayushkbhatia/Accrued/abacus-s34
created: 2026-11-10
updated: 2026-11-10
plan_key: A-01-T33
---

## Objective
Every listed artboard is locked at Tier C under 3 %, or its contract records a deviation saying
why it stays report-only, and axe stays clean.

## Built
- Gallery: AUD-02 a, c, d and e draw the live SHL-13 dock (`withAgentDock` over AUD-02's own
  scenario: the fixture runs' routes and the three agent flags, the cockpit flag kept), each with its
  run open (`AUD02_DOCK_RUN`: #4127 at 9:41 for a and d, the plan for c, the failed step for e).
  The unit scenarios in `fixtures/scenarios/AUD-02.ts` are unchanged (AUD-02's tests keep the v1 tab).
- Manifest: the `[data-cockpit='dock']` mask is dropped from a, c, d, e (spinner, shimmer and live
  dot masked instead). d is locked (1.09 % masked at S13). a, c, e stay report-only with the reason
  until the end-pass run measures them unmasked. b, g (3.13 / 3.14 %) and AUD-03 d, f (7.51 /
  3.18 %) are report-only with deviations; f stays report-only.
- Contracts: AUD-02 DV-13 and its parity table; AUD-03 DV-10 and its parity table.

## Progress log
- 2026-11-10: built; measured at the S34 end pass. If d measures over 3 % unmasked it returns to
  report-only with the figure; a, c, e lock if they measure under 3 %.
- Partial: b and g are not fixed (the Source Documents order is DEC-341's decision and the
  OverviewCard is shared); AUD-03 f's 3.18 % has no traced cause yet.
