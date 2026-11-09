---
id: TASK-6516
title: "P-10-T26: SSE core (kernel/realtime.py) and the run and badge streams"
spec: SPEC-647
acceptance_criteria: [AC-T1, AC-T2]
risk_zone: red
status: in-review
branch: s33-p10-t26
worktree: /Users/ayushkbhatia/Accrued/abacus-s33
created: 2026-11-09
updated: 2026-11-09
plan_key: P-10-T26
---

## Objective
A reconnect with Last-Event-ID receives every missed event in order, a new wall closes the stream
with locked within 60 s, and a seventh stream gets 409 too_many_streams.

## Plan (red)
1. `kernel/realtime.py` (new): framing (`id`/`event`/`data`, 64 KB → `ref_only`), per-process
   stream slots (6 per person, `too_many_streams`), `notify()` (`pg_notify` on 0683's
   `realtime_channel` inside the writing transaction, plus an in-process wake), and `stream()`:
   replay after the cursor, tail on a 1 s poll or a wake, re-authorise every 60 s and on wake
   (`locked`), `resync` on a gap, `:hb` every 15 s, close before an expiry.
2. `agents/run_stream.py`: `GET /v1/agent-runs/{id}/events` over `run_events` (`run_seq`; oldest
   kept 30 days → `resync`), authorised `agent_run.read`; `GET /v1/me/agent-badge` counts.
3. Routes behind `realtime.sse` (404 off).
Rollback: revert; nothing writes new rows.

## Progress log
- `2026-11-09` — Built; unit tests written, not run (end pass). Partial: the session stream
  (`/v1/sessions/{id}/events`) stays 501 until W-02's sessions exist; closing 30 s before token
  expiry needs the session's expiry on `AuthContext` (the stream takes it when present). The hub
  polls each second rather than holding a raw LISTEN connection (ADR-014); writers' `notify()`
  wakes in-process streams at once.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-3116 | The hub without a raw LISTEN connection; stream limits per process | no (ADR-232) |
