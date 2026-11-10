---
id: ADR-232
title: "Real time via SSE: identifier-only events through AbacusRouter, polling as the permanent fallback (extends ADR-013, ADR-023)"
status: proposed
date: 2026-11-06
deciders: ayushkbhatia  # solo edition; acceptance is his (red ADRs never default on silence)
risk_zone: amber
proposal: P-15
---

> **Instructions for coding agents**
> - Accepted ADRs are binding. Code that contradicts one must not be written.
> - If a task seems to require breaking an ADR, propose a new ADR that supersedes it. Never work around it silently.
> - Never edit an accepted ADR. Propose a new one that supersedes it.

**Status note.** Drafted by P-10-T58 (TASK-5105), from chapter 05 AG-06 and chapter 03 §7. The plan's
number for this proposal (ADR-156) is a P-ID alias: on `main` that number is another ADR, so
`docs/adr/backlog.md` gives this one.

## Context
SHL-04's bell, SHL-13's dock, WB-01 and WB-03 and the BND-02 live status all change while someone
watches them. `AbacusRouter` refuses WebSocket routes (`identity/routing.py`), and no endpoint may
carry client data outside the matrix. DEC-23 chose SSE, polling first. A stream that outlives an
authorisation is the risk: a wall or a revoked grant must end what the stream can show.

## Decision
1. **Transport.** Server-Sent Events over an ordinary `GET` through `AbacusRouter`, one matrix action
   per stream. WebSockets stay refused; there is no CRDT and no presence over the stream.
2. **Four streams.** `GET /v1/events` (action `events.subscribe`, the platform invalidation stream),
   and the run, session and badge streams of C6 v2 (actions `agent_run.read`, `session.read`).
3. **What an event carries.** Identifiers, enums and verified items only. An item that would hold a
   Restricted-tagged field travels as `{id, ref_only: true}` and is fetched through REST. Over 64 KB
   goes by reference. **No model token is ever streamed**; an item reaches a browser only after
   schema validation and citation verification (ADR P-46).
4. **Order and resume.** `run_seq` per run and `session_seq` per session, assigned in the writing
   transaction, `Last-Event-ID` scoped to the stream. No total order across runs. A gap older than
   the prune horizon answers `resync`. `realtime_events` keeps 24 hours, `run_events` 30 days.
5. **Authorisation lives.** A topic is authorised at subscribe through
   `notifications.register_topic(kind, authorizer)` and re-checked on `access.changed`: a wall or
   revoked grant sends `locked` and closes within 60 seconds. Portal principals reach only
   `portal:{grant_scope}` under `scope_only`; run and session streams answer 403.
6. **Limits.** A `:hb` heartbeat every 15 seconds; the server closes 30 seconds before token expiry;
   a seventh concurrent stream per user answers 409 `too_many_streams`; more than 500 queued events
   drop to `resync`; identical `(type, ref)` within 250 ms coalesce.
7. **Polling is permanent.** After three failures a client uses `refetchInterval` (2 s open run, 5 s
   open record, 30 s lists, 60 s bell). Every surface is correct on polling alone, and flag
   `realtime.sse` off answers 404 and clients poll: that flag is the kill switch.

## Options considered
### Option A: SSE through AbacusRouter, polling fallback — chosen
- Pros: one matrix action per stream; works through CloudFront and the ALB; no new dependency; a
  failed stream costs freshness, never correctness.
- Cons: one connection per tab per stream; edge timeouts need the heartbeat.

### Option B: polling only
- Why rejected: 2 s polling on every open dock is the larger load, and the bell misses its 2 s p95.

### Option C: WebSockets
- Why rejected: bypasses the route guard ADR-027 relies on, and nothing here needs client-to-server
  messages; commands stay ordinary POSTs under their own actions.

## Consequences
**Positive.** The matrix, `visible()` and audit rules apply unchanged. A surface never depends on a
stream to be right.

**Negative.** A held-open connection per viewer; heartbeats and token expiry need edge settings
(P-10-T15). A single subscriber writes `realtime_events`, so that writer is a known bottleneck.

**Follow-ups.** P-10-T05 (table), T26, T33 (streams), T15 (edge), RB-28 (kill switch).
