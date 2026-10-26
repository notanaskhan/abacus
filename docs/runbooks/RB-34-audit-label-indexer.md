---
id: RB-34
title: Audit label indexer failing, lagging or paused
owner: builder
alarms: []
last_rehearsed: never
rehearse_by: 2026-12-11
---
# RB-34 · Audit label indexer failing, lagging or paused

| Field | Value |
|---|---|
| Owner | builder |
| Severity range | SEV3 |
| Linked from | none yet (the `AuditLabelIndexer` Schedule's failed-run alert, when Q-01 adds one) |
| SLO affected | none directly: ADM-07's `q` search answers late, never wrong |
| Kill switches that apply | the Schedule's pause (`abacus_tools.schedules pause --id audit_labels:platform`) |
| Rehearse by | R1 (Fri Dec 11, 2026) |
| Last rehearsed | never |
| Last reviewed against an incident | never |

Written for the G-02-T10 follow-up (TASK-1355; DEC-436, DEC-453). `audit_event_labels` is a rebuildable projection of `audit_events`, the index ADM-07's `q` searches. The `AuditLabelIndexer` Schedule (`audit_labels:platform`, every 60 seconds, overlap SKIP, background queue) indexes each firm's new events, a few batches of 2,000 per firm per run. Every search also first catches its own firm up by one batch, so a stopped indexer makes a search slower, not wrong. The projection is never the record: `audit_events` is, and its hash chain (RB-29) is unaffected by anything here.

## 1. Recognise it
- `python -m abacus_tools.schedules show` (an ops task) lists `audit_labels:platform` paused, missing, or with failed recent actions;
- the worker logs `audit_labels.failed` with a `tenant_id` (one firm failing; the others still run);
- ADM-07 searches are slow for a firm with many new events (each search is catching up alone).

## 2. Act
1. A missing Schedule: `python -m abacus_tools.schedules ensure` restores it (it converges; an operator's pause survives).
2. One firm failing: read the error class in the log (never a label: none is logged). A label provider (`platform.audit_labels`) refusing a label is a labeler bug in its owning module; fix it there. The firm's search keeps working through the catch-up.
3. The indexer flooding the background queue: pause it (`abacus_tools.schedules pause --id audit_labels:platform --operator <handle> --reason "RB-34: <ticket>"`); searches still catch up per firm. Unpause when the cause is fixed.
4. A gap that the runs do not close (rows deleted, a labeler fixed and old labels wrong): rebuild the firm's index from the start with `audit_trail.api.backfill_labels(<tenant_id>)` in an ops task. It upserts, so it is safe to run while the Schedule runs; it waits for the firm's indexer lock and raises `IndexBusy` rather than claim it finished. An operator command for it is owed (G-02-T17's ops work).

## 3. Close
Confirm `schedules show` lists the Schedule unpaused with a recent successful run, and a `q` search on a fresh event of the affected firm finds it. Record the rehearsal date above.
