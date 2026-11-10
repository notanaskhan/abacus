---
id: TASK-6608
title: "P-10-T30: Frontend realtime client: app-core/realtime.ts on the generated fetch-based SSE runtime"
spec: SPEC-647
acceptance_criteria: [AC-T1, AC-T3, AC-T7]
risk_zone: green
status: in-review
branch: s34-p10-t30
worktree: /Users/ayushkbhatia/Accrued/abacus-s34
created: 2026-11-10
updated: 2026-11-10
plan_key: P-10-T30
---

## Objective
In Vitest a scripted invalidate refetches only matching query keys, three failures switch to
refetchInterval, and locked clears the cache and shows the not-allowed state.

## Plan
1. `apps/web/src/app-core/realtime.ts` (new): `RealtimeClient` over the generated SSE runtime
   (`client.sse.get` on `/v1/events`: bearer and tenant from the client's interceptors, backoff,
   `Last-Event-ID`), one per tab, `registerTopicKeys(kind, keys)` per domain, `invalidate`
   refetches only the mapped keys, `notice` the bell, `resync` every registered topic, `locked`
   clears the cache; after three failures `polling` with 5 s / 30 s / 60 s intervals.
2. `realtime-hooks.ts` (new): `useRealtimeStream(topics)` gated by `realtime.sse`,
   `useRealtimeStatus`, `useRealtimeInterval(kind)`.
3. `realtime.test.ts`: the row's three cases plus notice, live-without-polling and resync.

## Progress log
- `2026-11-10` — Built; prettier, tsc, eslint clean. Tests not run (end pass). Partial: no domain
  registers topic keys yet and nothing mounts `useRealtimeStream`; P-10-T35 (S35) swaps the dock
  to SSE and the domains register as they adopt it.
