---
id: RB-06
title: Queue backlog per work class
owner: builder
alarms: [SLO-05, SLO-07, schedule-to-start-ceiling]
last_rehearsed: never
rehearse_by: 2026-12-11
---
# RB-06 · Queue backlog per work class

| Field | Value |
|---|---|
| Owner | builder |
| Severity range | SEV3 to SEV2 |
| Linked from | SLO-05 (ceiling breached for 5 minutes), SLO-07 stalled mail queue |
| SLO affected | SLO-02, SLO-03, SLO-05, SLO-07 |
| Kill switches that apply | per-firm agent pause; Schedules pause (`abacus_tools.schedules pause`) |
| Rehearse by | R1 (Fri Dec 11, 2026) |
| Last rehearsed | never |
| Last reviewed against an incident | never |

Work runs on four work-class queues (`abacus-interactive`, `-time-sensitive`, `-background`, `-batch`) plus `abacus-keyops` (ADR-071). Each class has its own worker pool and concurrency limits; schedule-to-start is measured per class (`ScheduleToStartInterceptor`).

## 1. Recognise it
- The schedule-to-start metric for a class passes its ceiling (interactive 120 s) for 5 minutes; people wait on spinners; the canary's processing step times out.
- Temporal's task-queue view shows backlog on one queue. Which class matters: interactive is SEV2 in working hours; batch is a ticket.

## 2. Contain
1. Scale that class's worker service: `aws ecs update-service --cluster <cluster> --service <worker service for the class> --desired-count <n>` (the service's maximum is set in Terraform).
2. If a platform job is flooding a queue, pause its Schedule: `python -m abacus_tools.schedules pause --id <schedule id> --operator <handle> --reason "RB-06: <ticket>"` (an ops task; production through an ops request).
3. If one firm's agent work floods it, pause that firm's agents (its admin) and tell them.

## 3. Preserve
The queue's backlog graph, the worker services' CPU and memory, and the workflow types in the backlog (Temporal list by `TaskQueue`). No payloads (they are sealed anyway).

## 4. Assess
Is a worker pool down (RB-23), a dependency slow (database, scanner RB-24, provider RB-03), or real load (busy season)? Which firms wait?

## 5. Notify
Interactive backlog over 15 minutes in working hours: status page, "Accrued app", SEV2 template.

## 6. Recover
1. Once the backlog drains, return the desired count to its Terraform value (a drift otherwise).
2. Unpause any Schedule paused in step 2 (`abacus_tools.schedules unpause`).

## 7. Verify
Schedule-to-start back under target for 30 minutes; the canary passes twice.

## 8. Review
Typical actions: autoscaling on the backlog metric, a lower per-firm concurrency cap, moving a job to the batch class.

## Rehearsal log
| Date | Kind (drill, staging walk-through, tabletop) | Result | Changes made |
|---|---|---|---|
