---
id: RB-23
title: Workflow engine outage or worker disconnection
owner: builder
alarms: [SLO-05, readyz-temporal]
last_rehearsed: never
rehearse_by: 2026-12-11
---
# RB-23 · Workflow engine outage or worker disconnection

| Field | Value |
|---|---|
| Owner | builder |
| Severity range | SEV2 |
| Linked from | SLO-05, the `/readyz` Temporal check |
| SLO affected | SLO-03, SLO-05, SLO-07 |
| Kill switches that apply | Schedules pause |
| Rehearse by | R1 (Fri Dec 11, 2026) |
| Last rehearsed | never |
| Last reviewed against an incident | never |

Temporal Cloud runs every workflow; workers poll their class queues. A worker pool that stops makes its process exit non-zero so ECS restarts it (`abacus.worker`). Schedules catch up at most an hour of missed runs and skip while one is open (Q-01-T26).

## 1. Recognise it
- `/readyz` lists `temporal`; schedule-to-start climbs on every class; worker tasks restart in a loop.
- Temporal Cloud's status page, the namespace's metrics, or certificate and API-key expiry on the worker connection.

## 2. Contain
Nothing to switch off: requests that start workflows fail and say so; nothing is half-done (each start is idempotent by its workflow id).

## 3. Preserve
Worker logs (connection errors), the namespace metrics, the time window.

## 4. Assess
Temporal Cloud incident, our network (DNS Firewall allowlist, egress), or our credentials (the namespace API key in Secrets Manager, TLS). Which work is waiting.

## 5. Notify
More than 15 minutes in working hours: status page, "Agents & Workbench" and "Accrued app", SEV2 template.

## 6. Recover
1. Fix credentials or egress if ours; otherwise wait for Temporal Cloud.
2. Workers reconnect on restart; open workflows resume from their histories; Schedules catch up within their one-hour window, older missed runs are skipped (they are idempotent jobs).
3. Check the platform-job Schedules are still there: `python -m abacus_tools.schedules show` as an ops task; `ensure` restores any missing.

## 7. Verify
Schedule-to-start back under target; the canary passes twice.

## 8. Review
Typical actions: credential expiry alarms, a second region for the namespace (P-55 note).

## Rehearsal log
| Date | Kind (drill, staging walk-through, tabletop) | Result | Changes made |
|---|---|---|---|
