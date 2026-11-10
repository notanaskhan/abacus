---
id: TASK-6211
title: P-09-T05 E6 core, RunSource and RunStore
spec: SPEC-648
acceptance_criteria: [AC-8]
risk_zone: amber
status: in-review
epic: P-09
plan_key: P-09-T05
branch: s31-p09-t05
worktree: /Users/ayushkbhatia/Accrued/abacus-s31
created: 2026-11-08
updated: 2026-11-08
---

## Objective
Finish TASK-5001 (`runFeed.ts`, the PollingRunSource core inside a React Query hook): the
`RunSource` interface P-10's SSE source implements, `RunStore` on `useSyncExternalStore`,
`PollingRunSource` and `ScriptedRunSource` with `?static=1`.

## Plan (amber)
- `apps/web/src/domain/agents/runSource.ts`; exports from the domain's `index.ts`.
- The store reuses `applyItems` (seq order, once each, `resync` replaces).
- Scripted source: the handoff's `lib/agents.js` mechanics only; the script is a fixture's pages
  (AGENTS FE rule 5: never port kit sample data).
- Tests: `runSource.test.ts` (fake timers; run at the end pass).
- `useRunFeed` stays for the dock until P-09-T09 moves it onto the store.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-2811 | One source interface; scripts are fixtures; hidden tab pauses | no |
