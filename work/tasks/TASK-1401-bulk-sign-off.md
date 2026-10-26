---
id: TASK-1401
title: Bulk sign-off with Idempotency-Key, per item and atomic per item (P-04-T22, R-SO-7)
spec: SPEC-360
acceptance_criteria: [AC-2]
risk_zone: red
status: in-review
epic: P-04
plan_key: P-04-T22
branch: s11-review
created: 2026-10-27
updated: 2026-10-27
---

## Objective
`POST /v1/sign-offs:bulk` answers 501. Serve it: reviewers only, each target decided on its own
through the single sign-off path, per-item results with the fixed exclusion codes, and a replay
with the same `Idempotency-Key` returning the stored result. Acceptance: six workpapers with
three ineligible return three signed and three excluded with reasons, and a replay with the same
key returns the stored result.

## Plan
- **Service** `review/bulk.py`: a live human first; fresh MFA (403 `mfa_required`,
  `max_age_s`); `kernel.uow.idempotency.idempotent` keyed per (tenant, actor, route, key) with
  the request hash (a different body under the same key is 422 `idempotency_key_reused`). Each
  item: `sign_offs.sign_target` (its own unit of work, lock and rules) after
  `authorise(sign_off.bulk)` on the target's engagement; a refusal becomes the item's exclusion
  code; a hidden, walled or unknown target is `level_not_permitted` (no existence leak). Rows
  carry `bulk_request_id` (uuid5 of tenant, actor and key): a concurrent duplicate request finds
  the row already written for that request and reports it signed.
- **Matrix**: `sign_off.bulk` gains `mfa_recent: required`; `fresh-mfa-actions.yaml` lists it
  (group `sign_off`).
- **Static rule**: SIGNOFF-001 admits `review/bulk.py`.
- **Tests first**: `tests/integration/test_p04t22_bulk_sign_off.py`.
- **Rollback**: revert; the route answers 501 again. No migration.

## Progress log
- 2026-10-27: planned.
- 2026-10-27: built (acceptance tests written first, run in the end-of-batch targeted pass). Decisions DEC-500 to DEC-504; ED-150. Generated client and matrix regenerated.
