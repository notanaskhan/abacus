---
id: RB-10
title: Restore from backup
owner: builder
alarms: []
last_rehearsed: never
rehearse_by: 2026-12-11
---
# RB-10 · Restore from backup

| Field | Value |
|---|---|
| Owner | builder |
| Severity range | SEV2 to SEV1 |
| Linked from | none (drill) |
| SLO affected | SLO-11, SLO-12 |
| Kill switches that apply | read-only mode during the cutover (Q-01-T37, not built yet) |
| Rehearse by | R1 (drill, M4-05) |
| Last rehearsed | never |
| Last reviewed against an incident | never |

RDS PostgreSQL has point-in-time recovery for 35 days, cross-region automated backups to us-west-2 and a daily AWS Backup copy into the audit account's locked vault. A restore never overwrites: it creates a new instance. RPO 5 minutes (SLO-11).

## 1. Recognise it
Data was lost or corrupted (a bad migration that is not expand-only, an operator error under break-glass), or the instance is unrecoverable.

## 2. Contain
Stop writes to the damaged data: roll back the release that damages it (RB-01); read-only mode once Q-01-T37 lands.

## 3. Preserve
Take a manual snapshot of the damaged instance before anything else (`aws rds create-db-snapshot`), and record the time of the damage as precisely as the audit trail allows.

## 4. Assess
Pick the restore point: the latest time before the damage (the audit trail's `occurred_at` for the first bad event, minus a margin). Estimate what is lost after it.

## 5. Notify
A restore that loses customer writes is SEV1: RB-27 for each affected firm.

## 6. Recover
1. Restore to the chosen point as a new instance in the data subnets (not the drill subnet): `aws rds restore-db-instance-to-point-in-time --source-db-instance-identifier <instance> --target-db-instance-identifier abacus-<env>-restored-<date> --restore-time <iso> --db-subnet-group-name <data subnet group> --no-publicly-accessible`.
2. Verify it: `python -m abacus_tools.drill verify --env <env> --restored-host <endpoint> --restore-point <iso> --replica-bucket <bucket>` as an ops task (it only reads).
3. Cut over: change the database host in the environment's settings (Terraform variable, applied by hand) and force new deployments of the API and workers.
4. Keep the damaged instance until the review closes.

## 7. Verify
`/readyz` passes, the canary passes twice, the audit hash chain verifies (`make audit-chain-verify TENANT=<uuid>` for affected firms).

## 8. Review
Mandatory; the drill record (RB-15) gains the real timings.

## Rehearsal log
| Date | Kind (drill, staging walk-through, tabletop) | Result | Changes made |
|---|---|---|---|
