---
id: TASK-1443
title: Interim record-mode G8 and G9 providers, external release and external archive (A-01-T23)
spec: SPEC-330
acceptance_criteria: [AC-15, AC-16]
risk_zone: red
status: in-review
epic: A-01
plan_key: A-01-T23
branch: s11-assurance
created: 2026-10-27
updated: 2026-10-27
---

## Objective
"Meridian archives only against a fresh final export, becomes read-only, and keeps
`archive_locked_at` NULL." (A-01 §3.5 Stories 5.2 and 5.3; OQ-2, OQ-3; DEC-83, P-43.) Make
`POST /v1/audits/{id}/release-record` and `POST /v1/audits/{id}/archive-record` live, with the
`assurance_release_mode` firm setting, and answer a stale second factor with 403
`facts.reason = mfa_required` the way the export routes do (DEC-547), so the record dialogs open
the step-up only on that.

## Plan
- **Migration 0226** `assurance_external_records` (down_revision `0220`; the batch re-points):
  - `assurance_external_releases` (work item PK, tenant, engagement, `report_released_on`,
    `report_kind` opinion|no_report, `recorded_by`, `actor_kind = 'human'` CHECK, `mfa_at NOT
    NULL`, `recorded_at`), FK to `work_items (tenant_id, engagement_id, id)`.
  - `assurance_external_archives` (work item PK, tenant, engagement, `export_id` FK to
    `engagement_exports (tenant_id, id)`, `manifest_sha256` hex-64 CHECK,
    `firm_tool_ref_sealed bytea` bounded, `recorded_by`, `actor_kind = 'human'`, `mfa_at`,
    `recorded_at`).
  - Both: forced RLS (`tenant_table`), insert columns only, UPDATE/DELETE/TRUNCATE revoked and
    refused by an immutability trigger (`IMMUTABLE_TABLES`), an insert trigger binding
    `recorded_by` to the session's human actor (INV-1). The archive's insert trigger re-reads
    the export **FOR SHARE**: same tenant and work item, `kind = 'final_binder'`,
    `status = 'ready'`, not voided, not past `expires_at` on either clock, and the same manifest
    SHA-256 (data-layer re-check under lock).
  - `abacus_human_only_actions()` gains `assurance.release_recorded` and
    `assurance.archive_recorded` (yaml + codegen).
- **Firm setting** `defaults.assurance_release_mode` (`external` | `in_app`, unset reads
  `external`): the typed store of G-01-T04, so only `firm.manage_settings` (firm admin, fresh
  MFA) changes it, audited `firm_setting.updated`. `SettingKey` gains `choices` (identity).
- **`assurance/release.py`** (red): `record_release` (EP only by the matrix, fresh MFA via
  `authorise_fresh`, independence, a live person; 409 `release_mode_in_app`; 422
  `release_date_future` against `clock.today()`; 409 `record_out_of_phase` before In review or
  once released; the row, the derived move to Released through `advance_by_gate`, audit
  `assurance.release_recorded`). Composite G8 provider: met by SPEC-314's in-app release or an
  external release record.
- **`assurance/archive_gate.py`** (red): `record_archive` (EP or manager, fresh MFA,
  independence; `release_mode_in_app`; phase must be Released; evidence's
  `final_export_for_archive` locks the export FOR SHARE and checks it, 409
  `final_export_required` / `export_stale` with the newer event's sequence; the sealed firm-tool
  reference; the derived move to Archived; engagements' `archive_work_item` sets
  `work_items.archived_at` only (never `archive_locked_at`) and archives the engagement once all
  its work items are; audit `assurance.archive_recorded`). Composite G9 provider.
- **Freshness** (`evidence/export_currency.py`): a final export is current when the requester's
  selection now holds exactly the versions and request count the snapshot holds, and no change
  event (not a read) about any of its requests or versions was audited after `as_of_seq`
  (kernel `audit_newest_change`).
- **Routes**: the two stubs become live behind `audits.cockpit`, idempotent like the phase route;
  `authorise_fresh` (moved to `identity.api`, evidence keeps its name) answers `mfa_required`.
- **Read-only**: the engagement's `archived` status is what `authorise` reads (every write 403,
  layer attribute), the same lever SPEC-314's lock uses; nothing here sets `archive_locked_at`.
- **FE** (A-01-T24 dialogs): step-up only on `facts.reason = mfa_required`.
- **Contract** `audits-cockpit.md` §2, §6, §7, §12; SPEC-330 AC rows; DEC-590 to DEC-592.
- **Tests first**: `tests/integration/test_a01t23_record_mode.py` (acceptance against a real
  ready final export built by the workflow steps), contract stub tests move the two routes to
  live, `RecordDialogs` vitest.
- **Rollback**: revert the commits and downgrade 0226 (drops both tables, restores 0212's
  human-only list); the routes answer 501 again.

## Progress log
- 2026-10-27: planned and built (see the report for test and gate results).
