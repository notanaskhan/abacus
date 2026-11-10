---
id: TASK-6533
title: "P-09-T13: dock and trace fixture-to-live swap"
spec: SPEC-648
acceptance_criteria: [AC-1]  # the row's acceptance (Objective)
screens: [SHL-13, WB-09]
risk_zone: green
status: in-review
branch: s33-p09-t13
worktree: /Users/ayushkbhatia/Accrued/abacus-s33
created: 2026-11-09
updated: 2026-11-09
plan_key: P-09-T13
---

## Objective
On compose with the seeded tenant the dock and trace match the fixture scenarios field for field,
and with either flag off every host shows its designed flag-off state.

## Build
- `domain/agents/runFeed.ts`: `useRunFeed` now rides one `RunStore` per open run fed by
  `PollingRunSource` on the live C6 route (`GET /v1/agent-runs/{id}/items?after_seq=`, cursor,
  1.5 s, visible tab, stops on a terminal state). The pure feed helpers moved to `feedCore.ts`
  (re-exported) so the store and the source share them without an import cycle; a store error
  now re-renders its reader.
- AUD-02: the dock's step cards and the rail row stay in step by `work_item_ref` (the rail key):
  `selectedRef` / `onSelectRef` passed to the run pane.
- Notifications: `run_finished` and `run_needs_input` on an `agent_run` subject open the run's
  trace (`?ov=run-trace:<id>`) over the engagement (`feedHref`, `notificationHref`).
- ADM-07: a run event's "Run ›" and the drawer's "Open run" open the trace through the route's
  `useOpenTrace` (the planned span stays only where no run id or host exists).
- Flag-off: `agent_dock.enabled` off keeps the v1 run list (unchanged); `run_trace.enabled` off
  keeps the v1 trace (unchanged).
- Test `domain/agents/p09t13-live-swap.test.tsx`.

## Progress log
- `2026-11-09` — Built; tests written, not run (end pass). Partial: AUD-29's rows are P-05's
  screen (not built yet), so their trace link lands with it; the compose comparison against the
  seeded tenant is the end pass's dev-stack check.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-3133 | The feed's store and source share a pure core; run notifications open the trace | no |
