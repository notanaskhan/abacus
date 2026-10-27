---
id: TASK-1480
title: Audit export, AuditExportWorkflow and the signed manifest (G-02-T17; ADM-07 e, g)
spec: SPEC-349
acceptance_criteria: [AC-12, AC-13, AC-14, AC-45, AC-46, AC-47]
risk_zone: red
status: in-review
epic: G-02
plan_key: G-02-T17
branch: s12-gov
created: 2026-10-27
updated: 2026-10-27
---

## Objective
Make the stubbed `/v1/audit-events/exports` routes live: a person with `audit_event.export` and a
fresh second factor asks for a date range (at most 92 days); `AuditExportWorkflow` (batch) builds
`audit-log-<from>-<to>.csv`, `manifest.json` (format `accrued.audit-log-export` v1: SHA-256 of the
CSV, seq range, the P-43 checkpoint, the filter, the requester, row count) and `manifest.sig`
(ECDSA P-256 over the manifest, signed by the environment's KMS export-signing key), seals the
three in one ZIP in the exports bucket, and marks the job ready with a 7-day expiry.

## Plan
- **No migration**: `audit_exports` is 0192's (G-02-T10 made it for this task).
- **Signing** `audit_trail/export_signing.py`: `ExportSigner` protocol; `KmsExportSigner` (KMS
  `Sign`, `ECDSA_SHA_256`, `MessageType=DIGEST`, alias `settings().audit_export_signing_key_alias`);
  `LocalExportSigner` for local and test only (a P-256 key derived from the local master key);
  none configured: requests answer 503 before anything is written.
- **Storage** `audit_trail/export_store.py`: the A-01-T19 pattern (`settings().exports_bucket`,
  `kernel.crypto.seal` under the tenant key, segments bound to the export and position), prefix
  `audit-exports/<tenant>/<id>/`. audit_trail may not import evidence (ADR-008), so the pattern
  is copied, not imported. ADR-104: no presigned link; the API streams the ZIP.
- **Service** `audit_trail/exports.py`: request (idempotent on `Idempotency-Key`, audited
  `audit_export.requested`, dispatch after commit), status (the requester's own, 404 otherwise),
  link (fresh MFA; 409 `export_not_ready`, 410 `export_expired`), download (requester only, fresh
  MFA, audited `audit_export.downloaded` before the first byte, status `downloaded`).
- **Values (AC-14)**: the build reads as the requester (`identity.api.member_context`, reads only,
  no MFA time), through `explorer.shown_to` and `values.values_for`, so the CSV holds exactly
  what the requester sees on screen; a requester no longer a member fails the job.
- **Workflow**: `AuditExportWorkflow` (`audit_export:<tenant>:<id>`, batch): `audit_export.build`
  then `audit_export.mark_ready`, or `audit_export.mark_failed` on a decided failure.
  Replay histories recorded (`record_audit_export`), never hand-edited.
- **Route**: `GET /v1/audit-events/exports/{id}/download` (new, `audit_event.export`), contract
  first, `make generate`. The link answers this URL (`AuditExportLinkOut`, unchanged shape).
- **Terraform**: KMS `ECC_NIST_P256` `SIGN_VERIFY` key per environment and the worker's
  `kms:Sign` grant; `docs/operations/export-signing-keys.md` (the public key, published after the
  first apply: a human step).
- **Registries**: activity catalogue (`audit_export.failed`), target owner `audit_export`,
  notification `audit_export.ready` to the requester, WORKFLOWS and ACTIVITIES.
- **Tests**: `tests/integration/test_g02t17_audit_export.py`; `tests/workflows/test_audit_export_replay.py`.
- **Rollback**: revert the commits; the routes return to 501 and the table keeps its rows.

## Progress log
- 2026-10-27: plan written; built.
