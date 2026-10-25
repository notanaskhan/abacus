---
id: RB-11
title: Regional failover
owner: builder
alarms: []
last_rehearsed: never
rehearse_by: 2027-04-16
---
# RB-11 · Regional failover

| Field | Value |
|---|---|
| Owner | builder |
| Severity range | SEV1 |
| Linked from | none (tabletop) |
| SLO affected | SLO-13 |
| Kill switches that apply | read-only mode (Q-01-T37, not built yet) |
| Rehearse by | R2 (tabletop), then yearly |
| Last rehearsed | never |
| Last reviewed against an incident | never |

Primary us-east-2; pilot light in us-west-2: VPC and endpoints, ECS services at zero tasks, KMS replica keys, replica buckets (retention replicated) and secrets, cross-region automated database backups. Regional recovery under 8 hours (SLO-13). Rehearsed as a tabletop before R2; a live failover game day is Q-03's, yearly.

## 1. Recognise it
An AWS regional event in us-east-2 (AWS Health), with the API, database or storage unavailable for more than an hour and no recovery estimate.

## 2. Contain
Decide to fail over (the builder; record the time and the reason). Post the SEV1 status-page notice.

## 3. Preserve
Note the latest restorable time of the cross-region backups and the replication lag of the buckets at the decision.

## 4. Assess
Expected data loss (the backup lag), which firms have deadlines, how long us-east-2 is expected to be down.

## 5. Notify
SEV1 template; RB-27 for any firm whose recent writes may be lost.

## 6. Recover
1. Restore the database in us-west-2 from the cross-region automated backup (`aws rds restore-db-instance-to-point-in-time --region us-west-2 --source-db-instance-automated-backups-arn <arn>`).
2. Point the us-west-2 services at it and at the replica buckets; scale the services up from zero (`envs/production-dr`, applied by hand).
3. Move DNS for the firm and portal hosts to the us-west-2 load balancer origins.
4. Verify with the canary; then stay until us-east-2 is back and plan the return as a second, unhurried failover.

## 7. Verify
The canary passes in us-west-2; evidence opens through the replica keys.

## 8. Review
Mandatory; record measured times against SLO-13.

## Rehearsal log
| Date | Kind (drill, staging walk-through, tabletop) | Result | Changes made |
|---|---|---|---|
