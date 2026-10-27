---
id: TASK-1403
title: Firm export with dual approval (Q-02-T43; DEC-72, conflict C-11)
spec: docs/contracts/compliance-kernel.md §2 to §7
acceptance_criteria: [Q-02-T43]
risk_zone: red
status: in-review
epic: Q-02
plan_key: Q-02-T43
branch: s10-leftovers
created: 2026-10-27
updated: 2026-10-27
---

## Objective
The firm-export routes answer 501 behind `compliance.firm_export` (Q-02-T38 stub). Make them
live: a security admin asks for an export of all the firm's data and names a partner-level
approver; that second, distinct person approves (or declines); the approval starts
`FirmExportWorkflow`, which builds the archive (sealed under the tenant key in segments, with a
SHA-256 manifest); the requester or the approver then asks for a 15-minute link inside the 7-day
window, after which the link answers 410.

Acceptance (Q-02-T43): "A same-person approval is refused, a second distinct approver starts the
export, and the link stops working after 7 days."

Dependencies on main: Q-02-T30 (matrix rows `firm_export.*`, `fresh-mfa-actions.yaml`, the
`compliance.firm_export` flag, the C16 kinds `firm_export_approval_requested` and
`firm_export_ready`), Q-02-T38 (the stub and compliance-kernel v1.1), Q-01-T27 (tenant keys:
`kernel.crypto.seal` seals under the tenant's key; the multi-Region key itself is infrastructure).

## Plan
- **Migration 0216** (`down_revision = 0220`):
  - `firm_exports`: `requested_by` (`requested_by_kind = 'human'`), `request_mfa_at`,
    `approver_id`, `scope = 'all'`, `origin`, status `awaiting_approval` (default) to
    `building | declined`, `building` to `ready | failed`, `ready` to `downloaded`, `ready |
    downloaded` to `expired`. CHECKs: `approver_id <> requested_by`; a decision names
    `decided_by = approver_id`; a ready row carries its digests and `available_until`.
  - Data-layer binding (BEFORE INSERT and BEFORE UPDATE triggers, `search_path` pinned, actor
    from the session settings): the insert's actor is the requester, an active security admin;
    the approver is an active staff member who is a security admin or partner level. Only the
    named approver, as a person, decides; only the system moves `building` on and expires;
    `downloaded` is the requester's or approver's act. Stamps are written once.
  - `firm_export_links` (insert-only): one 15-minute link per issue, bound to the person, at
    most 15 minutes and never past the window (CHECKs and a BEFORE INSERT trigger that the
    export is ready or downloaded and the person is its requester or approver).
  - Forced RLS (`tenant_table`), minimal column grants, no DELETE.
- **Service** `evidence/firm_exports.py`: `request` (via `idempotent()`), `approve`, `decline`,
  `issue_link`, `exports` (last 12), every route `_human` then `authorise_fresh` on
  `Resource.firm` then the flag. The approver must differ (422 `approver_invalid`) and hold
  `firm_export.approve` (`member_could`, fresh MFA waived: they are not here). Approve and
  decline: the requester 409 `approver_must_differ`, anyone else 403, a decided export 409
  `export_not_awaiting_approval`.
- **Archive** `evidence/firm_export_build.py`: the skeleton package (DEC-508): a ZIP with
  `index.json` (format `0.1`, export id, firm, requester, approver, generated at, `packages: []`
  until Q-02-T47) and `manifest.json` (every other file's path, bytes, SHA-256);
  `manifest_sha256` is the manifest's digest, `bundle_sha256` the ZIP's. Stored by
  `export_storage.put_segments(kind="firm_export")` under `exports/<tenant>/firm-<id>/` with the
  binding `firm_export:<id>:<n>`.
- **Workflow** `FirmExportWorkflow` (`firm_export:<tenant>:<id>`, reuse rejected), v1 recorded:
  `firm_export.package` then `firm_export.mark_ready`, any build failure `firm_export.mark_failed`.
  Started by the outbox subscriber of `firm_export.approved`.
- **Download** (DEC-509): no presigned URL (ADR-104). The link is
  `/v1/firm/data-exports/{id}/links/{link_id}`, a new `GET` that streams the ZIP from the sealed
  segments for the signed-in person the link was issued to, re-authorised (fresh MFA, not
  offshore) and re-checked before each segment, with one `Range` (DEC-536 rules reused).
- **Expiry**: the daily `export_expiry:platform` sweep's activity also expires firm exports past
  `available_until` (activity code only; the workflow is unchanged); `firm_export.expired`
  deletes the segments. The link refuses from `available_until` on either clock regardless.
- **Audit** (catalogue entries): `firm_export.requested`, `.approved`, `.declined`, `.ready`,
  `.failed`, `.expired`, `.downloaded` (a link issued), `.streamed`. Outbox:
  `firm_export.requested` (notifies the approver), `.approved` (starts the build), `.ready`
  (notifies both), `.expired` (segments).
- **Registry, lists:** evidence `registry.py`; `schema_check.IMMUTABLE_TABLES` and its DB test;
  tenant-isolation list; worker subscriptions; notifications catalogue and its test; evidence
  `WORKFLOWS`/`ACTIVITIES`; replay test and recorder.
- **Contract:** compliance-kernel v1.3 (the archive route, the link shape), `make generate`.

## Tests
- `tests/integration/test_q02t43_firm_export.py` (acceptance first): `test_ac1_a_same_person_approval_is_refused`,
  `test_ac2_a_second_distinct_approver_starts_the_export`, `test_ac3_the_link_stops_working_after_7_days`,
  plus the SQL binding (requester as approver refused by the database; an approver not named
  refused by the guard), idempotent retry, tenant isolation, the stream and its 410.
- `tests/workflows/test_firm_export_replay.py` with recorded v1 histories.

## Rollback
Flag `compliance.firm_export` off (routes 404). Migration 0216 downgrades by dropping both tables
and their functions (no data outside them).

## Progress log
- 2026-10-27: plan written; build started (s10-leftovers).
