---
id: TASK-1445
title: Export download with Range, status and list routes, 7-day expiry sweep, void on withdrawal, export_ready notification kind, audit_trail read for the work item (A-01-T22)
spec: SPEC-344
acceptance_criteria: [AC-14, AC-15]
risk_zone: red
status: in-review
epic: A-01
plan_key: A-01-T22
branch: s11-engagements
created: 2026-10-27
updated: 2026-10-27
---

## Objective
"Downloads resume with Range, expire with 410 after 7 days, and a withdrawn file voids the ready
bundle." Builds on A-01-T18/T19 (#450, migration 0191).

## Plan
- **Already live, checked:** the status and list routes (`GET /v1/exports/{id}`,
  `GET /v1/work-items/{id}/exports`, A-01-T18) and the audit trail's read for the work item
  (`audit_trail.api.events_for_work_item`, G-02-T08, registered by the composition roots). No
  change beyond the download's `allowed_actions`.
- **Download** (`evidence/export_download.py`, new, red): `prepare` authorises per request
  (`export.download`: EP or manager, fresh MFA, independence, onshore, walls 404; the flag; the
  requester or an `export.create` holder), decides (409 `export_not_ready`; 410 `export_expired`
  from `expires_at`, `expired`, or withdrawn content, DEC-537), parses one `Range` (DEC-536; 416),
  writes `engagement_export_downloads` + audit `engagement_export.downloaded` in one unit of work,
  then `stream_bytes` decrypts segment by segment (no presigned URL, ADR-104). Route in
  `export_contract.py`: 200/206, `no-store`, `nosniff`, ETag, safe `Content-Disposition`.
  `identity/routing.py` gains the optional 416 response.
- **Expiry** (`evidence/export_lifecycle.py`, new): `ExportExpirySweep` workflow v1
  (`export_expiry:platform`, daily, background, ADR-090: recorded history
  `export-expiry-v1-swept.json`; added to the Schedule exact lists in
  `test_platform_schedules.py`, `test_platform_jobs_replay.py`, `record_platform_jobs.py`).
- **Void on withdrawal** (DEC-538): `evidence_version.withdrawn` subscriber `void_holding` (row
  locks), `mark_ready` re-checks after its lock (`settle_ready`), download refuses. New outbox
  events `engagement_export.expired` / `.voided`; their subscriber deletes the export's own
  segments (`export_storage.delete_segments`, prefix-bounded, segment keys only).
- **Notifications:** C16 kinds `export_ready`, `export_failed` (system, Download glyph), catalogue
  entries on `engagement_export.ready` / `.failed` to the requester only (walls at fan-out and
  read time); identifiers only. Email text is `notification.export_ready` content (staff import).
- **Audit:** `engagement_export.downloaded`, `.expired`, `.voided` in `activity_reviewed.py`; the
  target type `engagement_export` already has its owner.
- No migration (0191 has every column, the guard allows `ready -> expired` with a reason), no
  matrix row (A-01-T17 added `export.download`), no flag.
- **Tests:** `tests/integration/test_a01t22_export_download.py` (AC-14, AC-15, DEC-536),
  `tests/unit/evidence/test_export_range.py`, the schedule and replay lists, the catalogue unit.
- **Rollback:** revert the commit; the download answers 501 again; rows written stay valid
  (insert-only downloads; `expired` is a terminal status the guard already allowed).

## Progress log
- 2026-10-27: built the download, sweep, void, kinds; recorded the sweep's history; DEC-536 to
  DEC-538.
