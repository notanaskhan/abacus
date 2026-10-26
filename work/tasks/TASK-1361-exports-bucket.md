---
id: TASK-1361
title: The engagement exports bucket in Terraform, its task-role policies and its wiring (A-01-T18/T19 follow-up; DEC-433)
spec: SPEC-344
acceptance_criteria: [AC-6]
risk_zone: red
status: in-review
epic: A-01
plan_key: none (follow-up to A-01-T19)
branch: s10c-ops
created: 2026-10-27
updated: 2026-10-27
---

## Objective
`settings().exports_bucket` is read by `evidence/export_storage.py`, but nothing in `infra/`
defines the bucket or grants the API and worker access to it. Write the Terraform (plan only).

## Plan
- **Module** `infra/modules/s3-exports` (new; copies `modules/previews`, since `s3-evidence`,
  `s3-records` and `ecs-service` are still skeleton READMEs): `abacus-<env>-exports`, private
  (public access block, `BucketOwnerEnforced`), versioned (every bucket here is,
  `test_repository_files.py`), SSE-KMS under its own rotating key with bucket keys, TLS-only
  bucket policy plus a deny on Object Lock, retention, legal holds and ACLs; lifecycle: current
  objects expire after 7 days, noncurrent after 1, incomplete multipart uploads after 1, expired
  delete markers removed. No Object Lock.
- **Policies:** `abacus-<env>-exports-worker` (`s3:ListBucket` on the bucket with `s3:prefix`
  `exports/*`; `s3:PutObject`, `s3:GetObject`, `s3:DeleteObject` on `exports/*`;
  `kms:GenerateDataKey`, `kms:Decrypt` on the key via S3 for this bucket) and
  `abacus-<env>-exports-api` (`s3:GetObject` on `exports/*`, `kms:Decrypt` via S3). Object
  actions are scoped to the `exports/` prefix the store writes (tighter than `bucket/*`).
  Attached only when the task role names are set (`worker_task_role_name`,
  `api_task_role_name`, default null: the roles arrive with Q-01-T15).
- **Wiring:** `infra/envs/{staging,production}/exports.tf`; output `exports_task_environment`
  (`ABACUS_EXPORTS_BUCKET`, the setting `kernel/config.py` reads with its `ABACUS_` prefix) for
  the task definitions Q-01-T15 renders.
- **Tests:** `infra/tests/test_exports_bucket.py` (offline, on the `.tf` text).
- **Docs:** module README, `infra/modules/README.md`, env READMEs, `infra/README.md`
  "Exports bucket" (the builder's plan and apply per environment), DEC-454.
- **Rollback:** revert the commit; nothing is applied by a session.

## Not done (needs the builder)
- `terraform init`, `validate`, `plan` and `apply` per environment (`infra/README.md`,
  "Exports bucket"); setting `ABACUS_EXPORTS_BUCKET` in the API and worker environment and
  attaching the two policies until Q-01-T15 renders task definitions.

## Progress log
- 2026-10-27: written (DEC-454). `terraform fmt` clean; no init, validate or plan run (session
  rule). Offline tests in `infra/tests/test_exports_bucket.py`. Security review asked for the IAM
  and bucket policy.
