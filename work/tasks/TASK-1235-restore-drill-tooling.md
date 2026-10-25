---
id: TASK-1235
title: Restore-drill tooling, abacus_tools.drill verify and drill.yml (Q-01-T38)
spec: SPEC-050
acceptance_criteria: [AC-21]
risk_zone: red
status: done
epic: Q-01
plan_key: Q-01-T38
branch: s8b-platform-ops
created: 2026-10-25
updated: 2026-10-25
---

## Objective
Q-01 F9: "`drill.verify` checks per-tenant row counts against the source, `audit_events.seq` continuity per tenant, and a 1% (minimum 50) sample of evidence versions fetched from the replica bucket, unwrapped through the replica key and compared to `version.sha256`; it exposes a hook that recomputes seal manifests once P-43/A-07 create them. A planted fingerprint mismatch or sequence gap fails the drill." Acceptance: "A staging drill detects a planted fingerprint mismatch and a sequence gap and records restore-to-verified time against the 5-minute RPO."

## Plan (red zone)
- **Tool:** `backend/src/abacus_tools/drill.py`, `python -m abacus_tools.drill verify --env <env> --restored-host <host> --restore-point <iso> --restore-started-at <iso> [--rpo-lag-seconds N] [--settle-seconds 300]`. The source is the configured owner URL (`migrations_database_url`, read only); the restored instance is the same URLs with the host swapped (a PITR restore keeps roles and passwords), so no credential passes through the workflow.
  - Row counts: every insert-only table (`schema_check.INSERT_ONLY_TABLES`) with `tenant_id` and a creation timestamp (`created_at`, `occurred_at`, `recorded_at`), counted per tenant up to the cutoff (restore point minus the settle window, so a transaction still committing at the restore point is not a false mismatch). Tables that update or delete rows are not compared (the source has moved on); the report lists them as unchecked.
  - Sequence continuity: `audit_events.seq` is one global identity, so continuity is checked against the source: per tenant, the restored instance must hold every `seq` the source holds up to the cutoff; the first missing `seq` is named.
  - Evidence sample: 1% of evidence versions up to the cutoff, at least 50 (all when fewer), read through `evidence.storage.get` with storage on the replica bucket and the KMS key service on the replica region (the tenant aliases exist in both, P-65): the key and tenant binding, the envelope and the SHA-256 fingerprint and size are all checked there; any refusal is a mismatch.
  - Seal recompute hook: `register_seal_check(name, check)`; v1 registers `audit_chain` (`kernel.uow.chain.verify_chain` per tenant with checkpoints, on the restored instance). P-43/A-07 add seal manifests.
  - Report: JSON of codes, counts and identifiers only (tenant, version and table names; never content), with `restore_to_verified_seconds` and `rpo_ok` (`rpo_lag_seconds <= 300`). Exit 1 when anything fails.
- **Workflow:** `.github/workflows/drill.yml` (workflow_dispatch; production by default; concurrency `deploy-<env>`; the SSM deploy lock as `purpose: ops-task`; a random restore point in the last 7 days no later than `LatestRestorableTime`; `restore-db-instance-to-point-in-time` into the drill subnet group, not public, single AZ; the verify ECS task; timings in the job summary and a JSON artefact; the instance deleted and the lock released on every path). Never run in this lane.
- **Deploy lock:** `abacus_tools.deploy_lock` (take, release, show over SSM `/abacus/<env>/deploy-lock`; contract 3.4) is built here because drill.yml takes it; Q-01-T18's workflows and `make deploy-lock` reuse it.
- **Tests:** `tests/integration/test_drill_verify.py` (two throwaway Postgres databases, the S3 gateway and the local key service: a clean copy passes; a planted fingerprint mismatch, a sequence gap and a missing row each fail with their names; the sample size rule; timings and RPO in the report); `tests/unit/tools/test_drill_workflow.py` pins drill.yml's shape.
- **Rollback:** delete the tool and workflow; nothing else depends on them.

## Progress log
- 2026-10-25: plan written.
- 2026-10-25: built. Finding: the owner role is subject to forced row-level security, so a cross-firm count reads nothing; the drill instead lists the firms the platform created (`firm_provisioning_requests` and used signup codes, on either side, plus `--tenant`) and reads each firm's rows as the app role under that firm's own context (`tenant_session`), one database at a time (DEC-361). `audit_events.seq` is one global identity, so continuity is per firm against the source, not a gap-free range. Tests: `tests/integration/test_drill_verify.py` 8 passed (private Postgres plus a template copy as the restore; clean pass with tenants=1 and RPO ok; planted fingerprint mismatch names the version; planted sequence gap names the first missing seq and the count; a missing evidence row; RPO lag 301 s fails; sample size rule; URL host swap; report fields); `tests/unit/tools/test_drill_workflow.py` 9 and `tests/unit/tools/test_deploy_lock.py` 8 passed. Human to-dos before a real drill: per-environment GitHub variables listed in drill.yml's header; an `abacus-ops` task definition whose environment carries the owner and app database URLs (as for migrate), the replica bucket read and the replica-region `kms:Decrypt`; the drill subnet group and security group in Terraform (`infra/envs/production`); the deploy role allowed `rds:RestoreDBInstanceToPointInTime`, `rds:DeleteDBInstance` only on `abacus-drill-*`, `ecs:RunTask` on the ops task, and `ssm:PutParameter/GetParameter/DeleteParameter` on `/abacus/<env>/deploy-lock`.
