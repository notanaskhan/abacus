---
id: TASK-6625
title: "P-09-T19: journey E2E for the agent dock and run trace (j03 6 and 10, j18 5, j11 a4, j10 4)"
spec: SPEC-648
acceptance_criteria: [AC-1]
risk_zone: green
status: in-review
branch: s34-p09-t19
worktree: /Users/ayushkbhatia/Accrued/abacus-s34
created: 2026-11-10
updated: 2026-11-10
plan_key: P-09-T19
---

## Objective
The specs pass in fixture and compose modes and nightly on staging, and each fails if any decision
or sign-off row carries actor_kind agent.

## Built
- `apps/web/e2e/journeys/p09-agent-runs.spec.ts` on the journey harness (axe and INV-1 to INV-5 after
  every step; INV-1 fails a step whose decision or sign-off row carries actor_kind agent):
  j03 6 (projection by level, Open trace), j03 10 (the failed step, Retry, Open trace), j18 5
  (Thomas reads #4127's trace with no human-only control; Lena Park not allowed), j11 a4 (#4118's
  Timeline, Records read, Writes & approvals), j10 4 (Copperleaf Run 2's trace).
- `fixtures/screen-scenarios.ts`: "SHL-13" (AUD-02's run artboards with the dock live and the run
  open, `?dock=agent&run=`) and "WB-09" (the drawer over any firm page, `?ov=run-trace:<run>`; `n`
  answers 403). `agentScenario(…, forbidden)`.

## Progress log
- 2026-11-10: built; run at the S34 end pass.
- Partial (by rule, S34.md): j03 6's plan approval needs P-10-T33's plan routes (S35): fixme with
  its owner. Every step is fixture-only for now (fixme outside the fixture project): the runs are
  the fixture's until P-10 records them on the seeded tenant; staging nightly is not up.
- j18 5 opens WB-09 over the audits index rather than AUD-29 (WB-09's scenario has no audit id);
  the step checks the drawer, not the link that opened it.
