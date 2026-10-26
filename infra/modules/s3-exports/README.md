# s3-exports

The engagement export bucket `abacus-<env>-exports` (A-01-T18/T19, DEC-433; DEC-454). The worker's
`EngagementExportWorkflow` writes sealed 64 MiB segments under `exports/<tenant>/<export_id>/`
(`backend/src/abacus/modules/evidence/export_storage.py`); the API reads them back for the download
(A-01-T22). The app reads the bucket name from `ABACUS_EXPORTS_BUCKET` (`settings().exports_bucket`);
unset, an export build fails closed. `ABACUS_EXPORTS_BUCKET_OWNER` (the account number, set by the
operator from the vault, never in an output) makes every exports call send `ExpectedBucketOwner`.

- Private: public access block, `BucketOwnerEnforced`, TLS-only bucket policy, and a policy deny on
  Object Lock, retention, legal holds and ACLs (a transient copy, P-14: never a record).
- SSE-KMS with its own rotating customer-managed key (`alias/abacus-<env>-exports`), bucket keys on.
  The key policy lets the account administer the key but not use it; only the named task roles
  may encrypt, decrypt and generate data keys, through S3 in the region, for this bucket. The
  bucket policy refuses a put that names another key or another kind of encryption. Each segment
  is also sealed under the tenant's key by the app.
- Lifecycle: current objects expire after `expiry_days` (6) and the noncurrent copy 1 day later,
  so an export is gone within 7 days; incomplete multipart uploads after 1 day, expired delete
  markers removed.
- Task-role policies: `abacus-<env>-exports-worker` (`s3:ListBucket` on the `exports/` prefix;
  `s3:PutObject`, `s3:GetObject`, `s3:DeleteObject` on `exports/*`; `kms:GenerateDataKey` and
  `kms:Decrypt` through S3 for this bucket only) and `abacus-<env>-exports-api` (`s3:GetObject` on
  `exports/*`, `kms:Decrypt` through S3); every S3 statement requires `aws:ResourceAccount` to be
  this account. Until the role names are set, no one can use the key. They attach to the task roles named by
  `worker_task_role_name` and `api_task_role_name`; null until Q-01-T15 creates the roles.
- `task_environment` output: the `ABACUS_EXPORTS_BUCKET` entry for the API and worker task
  definitions.

Plan only from a session; the builder applies per environment by hand (`infra/README.md`,
"Exports bucket").
