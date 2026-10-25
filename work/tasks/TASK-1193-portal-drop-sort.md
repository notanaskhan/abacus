---
id: TASK-1193
title: Portal drop sort and upload limits (evidence) — drops route, v6 portal_drop_sort, drop poll, migration 0153 (R-01-T09)
spec: SPEC-323
acceptance_criteria: [AC-3]
risk_zone: red
status: in-progress
epic: R-01
plan_key: R-01-T09
branch: s8a-evidence-pipeline
created: 2026-10-25
updated: 2026-10-25
---

## Objective
SPEC-323 AC-3 is the section's routes; the drop sort's own acceptance is R-01 Story 2.1 and 2.3 (the epic), which the tests cite.

"The two estimated-payment files land on their request as rule links awaiting a person, Scan_0914.pdf waits in the inbox, and no drop ever links outside the dropper's scope."

## Plan (red zone)
- **Migration 0153** `portal_drop_sort` (down 0152): `inbox_files` + `channel`, `drop_batch_id`, `drop_binder_id`, `drop_key` (the per-file `Idempotency-Key`), `duplicate_of_version_id`, `sort_outcome` (written once, trigger `inbox_files_sort_once`); unique (batch, key) for drops; `inbox_files_one_waiting` holds for the firm channel only (a client duplicate is flagged, never refused). Rollback: `alembic downgrade 0152` (deletes portal-drop rows; local only).
- **Drop** `POST /v1/portal/binders/{id}/drops` (`evidence/drops.py`, served behind `portal.drop_sort`): `requests.api.drop_binder` authorises `evidence.upload` on the published binder with its client facts before the replay lookup (404 outside scope); the one upload policy (`uploads.screened`, unchanged) answered as 413 `file_too_large` / 415 `type_not_allowed` (the C5 contract's words; kernel `DomainTooLarge`, `DomainUnsupported`); content-addressed storage; duplicate flagged; `InboxFileAdded` starts processing. The edge lets the drop route answer its own oversize (`UPLOAD_ROUTE_PATHS`).
- **Sort** `upload_processing` v6 `workflow.patched("portal_drop_sort")` for inbox files, activity `upload.portal_drop_sort`: candidates from `requests.api.drop_items` (client-visible, open, no draft, not delegated), each kept only if `member_could(dropper, evidence.upload, item)`; `score_all` + `should_match`; decisive → version + `fulfil_by_rule` as a `SystemContext` for the dropper (run = the drop row; SYS-001 issuer registered for `evidence/drops.py`); else, a duplicate or the flag off → `waiting` + `portal.drop_unsorted` (catalogue kind `portal_drop_unsorted`, the engagement's leads). History `upload-processing-v6-portal-drop-sort.json`.
- **Poll** `GET /v1/portal/drops/{batch_id}`: the dropper's own files, re-authorised on the binder.
- **Tests:** `tests/integration/backfill/test_r01t09_portal_drops.py`, replay tests, `test_upload_policy`, catalogue and worker pins.

## Progress log
- 2026-10-25: built drop, sort, poll, migration and history; 7 integration tests and 18 replay tests pass. **Deferred (not built):** the staff void of a wrong rule link (`POST …/fulfilments/{id}/void` stays a 501 stub behind `portal.drop_sort`): it needs `fulfilments` void columns with a trigger, every fulfilment read path excluding voided rows and the inbox file returning to waiting, a second migration's worth of red work in `requests`; it goes with R-01-T15's suite or a follow-up row. Also deferred: `sort_outcome` `assigned`/`discarded` when a person sorts a waiting drop (the inbox status already says it), HEIC end-to-end (the policy's own unit tests cover the sniffing), the binder owner as the unsorted recipient (the engagement's leads for now; binders have no owner column).
- 2026-10-25 (close): full `tests/unit tests/contracts tests/security` 28,473 passed (2 C3/C5 stub tests updated to mark the served routes live, the repo's `LIVE` pattern); integration, workflow and hostile-file run 996 passed + `test_schema_check_db` 192 passed after pinning `inbox_files.sort_outcome`; `make check-fast` green.
- 2026-10-25 (security review): eight findings fixed in one commit, each with a test written first (DEC-321 to DEC-323 updated). Targeted suites 19,363 passed; `make check-fast` green.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-323 | Contract words for the one policy, the system context for the sort, what the drop stores | No (security review flagged: SYS-001 widened) |
