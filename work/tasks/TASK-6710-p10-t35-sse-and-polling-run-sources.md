---
id: TASK-6710
title: "P-10-T35: SseRunSource and PollingRunSource behind the E6 RunSource interface; /v1/me/agent-events badges; the dock on SSE behind realtime.sse with polling as fallback; aria-live on run-state changes only"
spec: SPEC-647
acceptance_criteria: [AC-T1, AC-T3]
risk_zone: green
status: in-review
branch: s35-p10-t35
worktree: /Users/ayushkbhatia/Accrued/abacus-s35
created: 2026-11-10
updated: 2026-11-10
plan_key: P-10-T35
---

## Objective
The dock fixture moves Dispatched, Running, Blocked from scripted SSE events with no polling request, and a killed stream falls back to 2 s polling without losing an event.

## Plan
1. `domain/agents/sseRunSource.ts` (new): `SseRunSource` on `GET /v1/agent-runs/{id}/events`
   through the generated client's SSE runtime (`onSseEvent` keeps event names); each event past the
   cursor (or `ref_only`) fetches its items with `after_seq`; `resync` refetches from 0; `locked`
   reports `RunStreamLocked` and stops; a terminal state stops; a dead stream falls back to
   `PollingRunSource` at 2 s from the same cursor. `runSourceFor` picks SSE behind `realtime.sse`.
2. `runFeed.ts`: `useRunFeed` takes its source from `runSourceFor` and returns the run-state
   announcement; `RunStateAnnouncer` (aria-live polite) in the dock card; items are never announced.
3. `agentBadge.ts`: `useAgentBadge` on `GET /v1/me/agent-events` behind `realtime.sse`.
4. Tests: `domain/agents/sseRunSource.test.ts`.

## Partial
- The badge hook is not mounted in the shell yet (the shell's badge counts still poll; mounting it
  is the shell's next touch). The run and session caches are patched through the store; TanStack
  query caches for run headers still refetch on the realtime client's invalidations (P-10-T30).

## Progress log
- `2026-11-10` — Built; tests written, not run (end pass).
