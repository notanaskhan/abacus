---
id: TASK-6517
title: "P-10-T27: GET /v1/events invalidation stream — subscriber, topics, coalescing, notice"
spec: SPEC-647
acceptance_criteria: [AC-T9]
risk_zone: amber
status: in-review
branch: s33-p10-t27
worktree: /Users/ayushkbhatia/Accrued/abacus-s33
created: 2026-11-09
updated: 2026-11-09
plan_key: P-10-T27
---

## Objective
request_item.status_changed reaches engagement and work_item subscribers as identifiers only, a
firm admin gets metadata topics only, and a portal principal can subscribe only to its own grant
scope.

## Plan (amber)
1. `kernel/realtime.py`: the topic slot (`register_topic`, `authorise_topic`; fail closed) and
   the invalidation registry (`register_invalidation`). The slot is in the kernel because nothing
   may import `notifications` (module graph); ADR-232's `notifications.register_topic` reads it.
2. `notifications/realtime.py`: the subscriber (one `realtime_events` row per named topic in a
   unit of work, `realtime.invalidated` audited, then `notify`), the stream (`stream` event first,
   replay after Last-Event-ID, metadata topics carry `notice`/`locked`/`resync` only, identical
   `(topic, type, ref)` coalesce per read, over 500 waiting → `resync`), `change_topics`
   (the caller's own stream), the `user` and `firm:home` topics, and three invalidations
   (`request_item.status_changed`, `report.released`, `notification.created`).
3. Owners register topics: `engagements/realtime_topics.py` (engagement, work_item: content for
   `engagement.read`, metadata for a firm admin), `agents/realtime_topics.py` (run),
   `portal/realtime_topics.py` (a client principal's own grant scope).
4. Routes behind `realtime.sse`.
Rollback: revert.

## Progress log
- `2026-11-09` — Built; unit tests written, not run (end pass). The R-02-T15 notification line
  (`TEMPLATES["uncorrected_misstatements.acknowledged"]`) was missing and broke the email map at
  import; fixed in this commit — move the hunk to R-02-T15's commit at restack. The session topic
  waits for W-02 sessions.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-3117 | The topic slot in the kernel, metadata topics, coalescing | no (ADR-232) |
