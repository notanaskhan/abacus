---
id: RB-15
title: Disaster-recovery drill procedure
owner: builder
alarms: []
last_rehearsed: never
rehearse_by: 2026-12-11
---
# RB-15 · Disaster-recovery drill procedure

| Field | Value |
|---|---|
| Owner | builder |
| Severity range | SEV2 (a failed drill) |
| Linked from | none (drill) |
| SLO affected | SLO-11, SLO-12 |
| Kill switches that apply | none |
| Rehearse by | R1 (Fri Dec 11, 2026) |
| Last rehearsed | never |
| Last reviewed against an incident | never |

Proof, not configuration (ADR-093, ADR-096): a restore is drilled every quarter, the first by Fri Dec 11, 2026 on the production canary (Q-01-T39), then Q-03's quarterly drills. A failed drill is SEV2 and blocks the next production release.

## 1. Recognise it
The quarter's drill is due (`docs/ops/drills/`), or a change to backups, keys or replication needs proof.

## 2. Contain
Choose a time outside deploy windows; the drill shares the environment's deploy concurrency group and lock, so it never overlaps a deploy.

## 3. Preserve
Nothing to preserve: the drill reads only.

## 4. Assess
Confirm the drill's environment variables exist (drill.yml header) and the latest restorable time is recent (RPO lag under 5 minutes).

## 5. Notify
None. The drill runs inside the production account; production data never leaves it (ADR-087).

## 6. Recover (run the drill)
1. Actions, `drill`, Run workflow: environment `production` (or `staging` for a rehearsal), restore point empty (a random point in the last 7 days).
2. It takes the deploy lock, restores `abacus-drill-<run>` into the drill subnet, runs `abacus_tools.drill verify` as an ops task (per-firm row counts and audit sequence against the source, a 1% minimum-50 evidence sample from the replica bucket through the replica key, the audit hash chain), records the timings, deletes the instance and releases the lock, on every path.
3. Copy the job summary and the `drill-record` artefact into `docs/ops/drills/<year>-Q<n>.md`: times and results only, never data.

## 7. Verify
The run is green; the record shows restore-started, available and verified times, the RPO lag under 300 seconds, zero mismatches; `aws rds describe-db-instances --db-instance-identifier abacus-drill-<run>` finds nothing.

## 8. Review
A failure opens a SEV2 and RB-10's questions; a passing drill updates "Last rehearsed" here and in RB-10.

## Rehearsal log
| Date | Kind (drill, staging walk-through, tabletop) | Result | Changes made |
|---|---|---|---|
