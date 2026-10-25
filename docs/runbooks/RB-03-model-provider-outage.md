---
id: RB-03
title: Model provider outage
owner: builder
alarms: [SLO-04, model-route-outage]
last_rehearsed: never
rehearse_by: 2026-12-11
---
# RB-03 · Model provider outage

| Field | Value |
|---|---|
| Owner | builder |
| Severity range | SEV3 to SEV2 |
| Linked from | SLO-04, the gateway's outage block metric |
| SLO affected | SLO-04 |
| Kill switches that apply | platform AI pause and model-route block (Q-01-T36, not built yet); per-firm agent pause (`POST /v1/firm/agents/pause`, a firm admin with fresh MFA) |
| Rehearse by | R1 (Fri Dec 11, 2026) |
| Last rehearsed | never |
| Last reviewed against an incident | never |

The gateway admits each model call on an approved route only (ADR-113: client data stays on Bedrock; never rerouted). On a 5xx, timeout or connection error it blocks that route's model for `outage_block_seconds` (30 by default) and the run ends in its degraded state; work is queued, not lost.

## 1. Recognise it
- Agent runs end `failed` or stay queued; SLO-04 (interactive screening) burns; the canary's screener step fails on `client_data` environments.
- Gateway metrics show `refused` with reason `unavailable` for one route, or provider error rates rise. Check the provider's status page (Bedrock: the AWS Health Dashboard for us-east-2).
- Not this scenario: budget refusals (RB-07), a boundary refusal (`data_boundary`: settings, not an outage).

## 2. Contain
Nothing to reroute: client data never moves off Bedrock (ADR-113). If calls keep failing and costing retries, pause agents for the affected firms (a firm admin, or the platform switch once Q-01-T36 lands). Interactive users see the degraded state already.

## 3. Preserve
Usage records for the window (`usage_records`: route, outcome, counts; no prompts), the gateway logs' error classes, the provider's incident reference.

## 4. Assess
Which route and model, since when, which firms had runs fail (tenant UUIDs), and whether any deadline work is waiting. Throttling (quota) is not an outage: request a quota increase (F-09 vendor ticket) and lower concurrency.

## 5. Notify
More than 30 minutes during working hours: status page, "Agents & Workbench" component, SEV2 template.

## 6. Recover
1. When the provider recovers, the outage block expires by itself; queued work resumes from its work slots.
2. Runs that ended `failed` are re-run by the person (or the engagement agent's next tick); nothing is re-run automatically on someone's behalf.

## 7. Verify
New runs complete; SLO-04's burn stops; the canary's screener step passes on its next run.

## 8. Review
Typical actions: an alert on the outage-block counter, a lower retry budget, a quota request filed ahead of busy season.

## Rehearsal log
| Date | Kind (drill, staging walk-through, tabletop) | Result | Changes made |
|---|---|---|---|
