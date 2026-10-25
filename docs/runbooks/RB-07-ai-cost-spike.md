---
id: RB-07
title: AI cost spike
owner: builder
alarms: [cost-anomaly, budget-soft-crossed]
last_rehearsed: never
rehearse_by: 2026-12-11
---
# RB-07 · AI cost spike

| Field | Value |
|---|---|
| Owner | builder |
| Severity range | SEV3 |
| Linked from | the hourly spend-anomaly job (`budget.anomaly`), a firm's soft budget crossed |
| SLO affected | none |
| Kill switches that apply | per-firm agent pause; the platform AI pause (Q-01-T36, not built yet) |
| Rehearse by | R1 (Fri Dec 11, 2026) |
| Last rehearsed | never |
| Last reviewed against an incident | never |

Budgets are enforced before every model call (SPEC-007): firm, engagement and platform hard limits refuse; soft limits alert. The hourly `SpendAnomalyWorkflow` (Schedule `spend_anomaly:platform`, Q-01-T26) flags engagements spending past the anomaly multiple: it alerts and never blocks.

## 1. Recognise it
- `budget.anomaly` audit events in a firm's trail and the `abacus.budget.anomaly` metric; `budget.soft_crossed` warnings; the AI cost dashboard rises.
- Confirm in `usage_records` (by engagement and agent, identifiers only) which agent and route spend.

## 2. Contain
Ask the firm admin to pause agents for the firm (or pause the engagement's agent); the hard limits already stop runaway spend at the firm's cap. A platform-wide stop is the AI pause once Q-01-T36 lands.

## 3. Preserve
The usage rows for the window and the runs that spent (ids). No prompts or outputs in tickets.

## 4. Assess
A loop (the same run retrying), a change in a prompt or model tier, or genuine work? Which firm pays (the firm's plan) and whether the platform cap is near.

## 5. Notify
The firm's admins in-app if their agents were paused. No status-page notice.

## 6. Recover
Fix the loop or the prompt in code; the firm admin resumes agents; check the next hour's anomaly run is clean.

## 7. Verify
The next `spend_anomaly:platform` run flags nothing for that engagement; spend per hour back to its baseline.

## 8. Review
Typical actions: a per-run cost ceiling, a retry cap, a cost baseline update (Q-02).

## Rehearsal log
| Date | Kind (drill, staging walk-through, tabletop) | Result | Changes made |
|---|---|---|---|
