---
id: TASK-7421
title: "P-10-T50: Playwright on staging: apps/web/e2e/agents/run-stream.spec.ts (dock over SSE, polling fallback, locked on wall) and the j23 1-run step; j11 b2-b3 kept as test.fixme until W-02"
spec: SPEC-647
acceptance_criteria: [AC-T1, AC-T2, AC-T3, AC-W4]
risk_zone: green
status: in-progress
branch: s38-p10-t50
worktree: /Users/ayushkbhatia/Accrued/abacus-s38
created: 2026-11-12
updated: 2026-11-12
plan_key: P-10-T50
---

## Objective
The specs pass on staging with assertInvariants and axe clean, and the fixme steps are listed in the
journey manifest.

## Built
- `apps/web/e2e/agents/run-stream.spec.ts`: j23 1-run on AUD-02 c and d (fixture project); the dock
  over SSE within 2 s, the polling fallback with `/v1/events` refused, and the locked session on
  the hosted projects; j11 b2 and b3 `test.fixme` naming W-02. Each step runs through the journey
  harness (axe and INV-1 to INV-5).
- `playwright.config.ts`: `**/agents/**/*.spec.ts` joins the harness projects (fixture, fullstack,
  staging, canary) and stays out of the chromium project.
- `e2e/journeys/README.md` (the journey manifest) lists the fixme steps and their owners.

## Partial (status in-progress)
- "Pass on staging": the hosted runs skip while `ABACUS_STAGING_URL` is unset; they run at the S38
  close's staging deploy (one deploy for the batch). The locked session is fixme until W-02's WB-01 g.

## Progress log
- `2026-11-12` — Written (S38); `playwright test --list` finds the six tests.
