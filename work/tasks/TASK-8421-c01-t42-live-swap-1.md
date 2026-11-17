---
id: TASK-8421
title: "C-01-T42: Live swap 1 (CLS-01, 02, 03, 09)"
spec: SPEC-655
acceptance_criteria: [AC-1, AC-28]
risk_zone: green
status: in-review
branch: c01-t42-live-swap-1
worktree: /Users/ayushkbhatia/Accrued/abacus-s48
created: 2026-11-17
updated: 2026-11-17
plan_key: C-01-T42
---

## Objective
Spec section: docs/plan/epics/C-01.md §5. Live swap 1: CLS-01, CLS-02, CLS-03 and CLS-09 from fixtures to live endpoints; runs through SseRunSource with the polling fallback; C-20 error, not-allowed and flag-off states; deep links and link-contract entries.

## Plan (green)
1. `domain/closes/states.ts`: `closeReadState` (403 restricted role, 404 restricted walled, else error with Retry) and `runIsLive`/`RUN_POLL_MS`.
2. CLS-02 shell: restricted and error frames with no record data; Overview: the run read polls every 2 s while live without SSE, a `RunWake` on `useRunFeed` (SseRunSource behind `realtime.sse`) invalidates the run reads on each item; start and retry refresh the runs.
3. CLS-03 and CLS-09: the same frames (CLS-09's 404 stays the empty plan).
4. CLS-01 opens CLS-02 and CLS-09 through `to.CLS02` / `to.CLS09` (link contract rule 1); the route no longer passes those handlers.
5. Manifest: CLS-01, 02, 03 and 09 live; CLS-10's contract names its links (rule 5).
6. Tests: `domain/closes/states.test.ts`; link-contract test passes (20/20).

## Progress log
- `2026-11-17` — Built in the S48 sequential stack. tsc, eslint, prettier clean; link-contract.test.ts 20 passed. Not done here: the acceptance's staging run with the fake QBO (a human step on staging) and the full-stack screen specs. Gates and tests run once at the S48 end pass (build first, test last).
