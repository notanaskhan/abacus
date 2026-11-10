---
id: RB-69
title: "Agent dock and trace: degraded (SHL-13 run pane, WB-09 run trace)"
owner: builder
alarms: []
last_rehearsed: never
rehearse_by: 2027-12-17
---
# RB-69 · Agent dock and trace: degraded

| Field | Value |
|---|---|
| Owner | builder |
| Severity range | SEV3 (the dock lags or the trace is slow) to SEV2 (no run is visible to the people who must decide) |
| Source | P-09-T20; SPEC-648; P-09 §5, §8; flags `agent_dock.enabled`, `run_trace.enabled` |

The dock and the drawer only show what runs did and what waits on a person. They never decide,
so degrading them never changes a record: the decision rows, sign-offs and audit trail stay where
they are, and every human action has a page of its own (SHL-10, SHL-11, the workpaper headers).

## 1. Detect
Two signals (OpenTelemetry, exported with the service's metrics; dashboards below):
- **Poll rate.** `abacus.agent_run.items_polls` (counter; attributes `state`, `empty`). A healthy
  feed polls at 1.5 s per open dock while its run is `queued` or `running` and never after a
  terminal state. Degraded: polls on terminal runs (`state` in succeeded, failed, needs_input)
  above zero for 10 minutes (a client that never stops), or the total above 4 per second per
  tenant (open docks in hidden tabs: the client pauses them).
- **Trace latency.** `abacus.agent_run.trace_latency` (histogram, seconds). Budget: p95 at most
  0.8 s, p99 at most 2 s, over 15 minutes. Degraded: p95 over budget for 15 minutes.

## 2. Triage
- Polls on terminal runs: a client build regression in `PollingRunSource` (P-09-T05); P-09-T17's
  suite names the rule. Check the web release that went out last.
- Too many polls: count open docks (`state=running`, `empty=true` dominates). A runaway is a tab
  left open on many runs; the server answers each poll from the index, so the cost is load, not
  correctness.
- Slow traces: a run with a very long history (records read in the thousands), or the database.
  Check RB-06 (queue backlog) and RB-23 (workflow engine) first: a slow trace usually follows them.

## 3. Contain
- `run_trace.enabled` off for the firm: the drawer keeps its v1 trace and the step-detail route
  answers 404. Nothing else changes.
- `agent_dock.enabled` off for the firm: the Agent tab shows the v1 activity list; the dock pane,
  the run picker and the agents strip go. Decisions stay on their own pages.
- Neither flag stops a run. To stop runs, use RB-39 (stage demotion) or the run's own Stop.

## 4. Communicate
Firm-facing only if a flag is turned off for a live firm: the firm's admin is told the dock is
paused and where decisions wait (the inbox, SHL-10). No client sees the dock or the trace.

## 5. Recover
1. Fix the cause (roll back the web release for a client regression; RB-01).
2. Turn the flag back on for the firm; open a run in the dock and its trace on staging first.
3. Watch the two signals for 30 minutes.

## 6. Verify
Polls on terminal runs are zero; trace p95 is under 0.8 s; a dock on a running run updates within
two polls; the trace opens on a finished run with its three views.

## 7. Review
Each finding becomes a test (P-09-T17's suite for the client rules), an alarm or an ADR.

## Dashboards
One dashboard, "Agent dock and trace", per environment, from the service's OTel metrics:

| Panel | Metric | Statistic | Line |
|---|---|---|---|
| Polls per second, by run state | `abacus.agent_run.items_polls` | sum / 60 s, grouped by `state` | 4 per second per tenant |
| Polls on terminal runs | `abacus.agent_run.items_polls` where `state` in succeeded, failed, needs_input | sum per 5 min | 0 |
| Empty polls share | `abacus.agent_run.items_polls` `empty=true` over all | ratio | none (context) |
| Trace latency | `abacus.agent_run.trace_latency` | p50, p95, p99 per 5 min | p95 0.8 s, p99 2 s |
| Trace reads | `abacus.agent_run.trace_latency` | count per 5 min | none (context) |

The dashboard and its two alarms are Terraform in `infra/modules/observability` when Q-01's module
lands (it is a skeleton today); until then this table is the definition, and the alarms list above
stays empty (ADR-098: an alarm names its runbook once it exists).

## Rehearsal log
| Date | Kind (drill, staging walk-through, tabletop) | Result | Changes made |
|---|---|---|---|
