---
id: RB-28
title: "Real-time delivery degraded: the event stream is slow or down and clients fall back to polling"
owner: builder
alarms: [SLO-06, sse-delivery-p95, db-connections-70]
last_rehearsed: never
rehearse_by: 2028-04-14
---
# RB-28 · Real-time delivery degraded

| Field | Value |
|---|---|
| Owner | builder |
| Severity range | SEV3 (delivery p95 over 5 s, or streams dropped and clients polling) to SEV2 (polling also failing: no live run updates and stale lists) |
| Source | P-10-T51 (DEC-4412); SLO-06 in `docs/ops/slos.md`; SPEC-647 §3.8; P-10-T26/T27 |
| Alarms | `abacus-staging-sse-delivery-p95` (SLO-06), `abacus-staging-db-connections-70` |
| Related | RB-65 (the SSE edge path), RB-23 (workflow engine), RB-01 (deploy and rollback) |

## What "delivered" means
A write commits a `realtime_events` row (the outbox subscriber, one per topic) and wakes the
topic. Each stream re-reads its topics and sends the rows as `invalidate` events; the browser
refetches through REST. The API logs `realtime.delivered` (counts and milliseconds only) on each
tail read that sends events, with `lag_ms`: the oldest sent row's age on the database clock.
CloudWatch turns those lines into `Abacus/Realtime SseDeliveryLagMs`; the alarm fires when its p95
is over 5,000 ms for three 5-minute periods. A replay after `Last-Event-ID` is not counted.

Nothing is lost when delivery is slow or the stream is off: the client polls its open queries
every second while the stream is down (SPEC-647 §3.8) and every list is read from REST. The
SLO is a ticket, not a page, for that reason.

## Triage (first 10 minutes)
1. **Is it the stream or the database?** Open the `SseDeliveryLagMs` p95 and the RDS
   `DatabaseConnections` maximum side by side for the last hour.
   - Lag up, connections near 70%: the stream reads are queueing for a connection. Go to *Database
     pressure*.
   - Lag up, connections normal: the outbox subscriber is behind (rows are written late) or the
     API tasks are CPU-bound. Go to *Subscriber or API behind*.
   - No `realtime.delivered` lines at all while clients are open: the stream path is down. Go to
     *Streams down*.
2. **Who is affected?** All firms, or one tenant? `realtime.delivered` carries no tenant; read the
   API's `stream` 409 count (`too_many_streams`) and the ALB's 5xx on `/v1/events` instead.

## Database pressure
1. Count streams: each open stream holds no connection between reads, but every read takes one.
   A wake storm (many writes on one engagement topic) makes every stream on it read at once.
2. Raise the read interval only if it is the cause: `realtime.POLL_SECONDS` is code; ship it as a
   fix, not a hot edit. Meanwhile, if connections pass 85%, turn `realtime.sse` off (below): the
   clients' 1 s polling is cheaper per request than a wake storm across hundreds of streams.
3. Check for a long transaction holding connections (`pg_stat_activity`, state `idle in
   transaction`) from a worker; that is RB-23's area, not this one.

## Subscriber or API behind
1. The outbox relay's backlog: if events are committed but `realtime_events` rows arrive late,
   the relay is behind (RB-06). The stream cannot be faster than the relay.
2. API CPU over 80% on every task: scale the API service out (desired count +1) through the
   staging apply role; the streams rebalance as clients reconnect.

## Streams down
1. Check RB-65 first: the CloudFront behavior, the ALB idle timeout and the WAF rule.
2. If the API answers `GET /v1/events` with 5xx, roll back the last deploy (RB-01).

## Turn the stream off (fallback to polling)
The flag `realtime.sse` (Jan 27, 2028 train) is the switch. Off, `GET /v1/events` answers 404 and
every client polls. Turn it off through the firm-admin flag screen with a reason, or for every
firm with `make flag FIRM=<tenant_id> FLAG=realtime.sse VALUE=false OPERATOR=<name> REASON=RB-28` (SPEC-011); turn it back on once the cause is fixed. No data is at
risk either way.

## Rehearsal (P-10-T51, on staging)
Run during the runtime load test (`python -m abacus_tools.loadtest.run runtime_v2`, the
synthetic firm PF-X1 only):
1. At minute 10, with 1,500 streams open, turn `realtime.sse` off.
2. Expect: streams close, `realtime.delivered` lines stop, clients poll (the API's request rate
   on the list routes rises), no 5xx on the list routes, no error in the browser console of an
   open run dock.
3. At minute 15 turn it back on. Expect: clients reconnect with `Last-Event-ID`, receive what they
   missed in order, and `SseDeliveryLagMs` p95 returns under 2,000 ms within 5 minutes.
4. Record the times, the peak `DatabaseConnections` and the p95s in the load report, set
   `last_rehearsed` above, and file a dated fix for any target missed.

## Roll back
The alarms and the metric filter are `infra/envs/staging/realtime_slo.tf`; removing them is a
Terraform change. The stream is rolled back by the flag, never by a migration.
