---
id: TASK-1002
title: Content hash and staleness — review.hashing (RFC 8785, in-house), ReviewableFacts, computed staleness query, golden vectors (P-04-T14)
spec: SPEC-308
acceptance_criteria: [AC-5]
risk_zone: red
status: done
epic: P-04
plan_key: P-04-T14
branch: s6-review-integrity
created: 2026-10-24
updated: 2026-10-24
---

## Objective
"Golden vectors hash identically through the helper and the owner adapters, and a sign-off reads stale exactly when the target hash differs." (P-04-T14.)

## Plan (red zone)
- **Code:** `review/hashing.py` — `canonical_json` (RFC 8785: UTF-16 member order, ECMAScript number form, minimal escapes; refuses NaN, infinities, integers past 2**53 - 1, `Decimal`, non-string names and lone surrogates) and `content_hash` (SHA-256 hex). No dependency.
- **Slot:** `review/slots.py` — `ReviewableFacts(target_type, target_id, engagement_id, content_hash, version_no, preparer_user_ids, required_levels, locked)`, `register_reviewable_facts`, `reviewable_facts` (fail closed: 422 `unregistered_kind`, 404 for an unknown target or a provider answering for another), `reviewable_fact_types`.
- **Staleness:** `review/repository.stale_sign_offs` (one query: newest sign-off per target and level, DISTINCT ON, joined to the current hashes through `unnest`, `content_hash <>`), `review/service.stale_of` → `StaleSignOff`. LIST-001 exemption beside `sign_offs_of` (same authorisation).
- **Owner adapter:** `workpapers.service.content_hash` delegates to `review.api.content_hash`; `workpaper_facts` registered for `workpaper`.
- **No migration, route, matrix or flag change.** Rollback: revert the commit.
- **Tests:** `tests/unit/review/golden/hash_vectors.json` (the two RFC 8785 §3.2.3 examples, ECMAScript numbers, a decimal field value, two workpaper contents); `tests/unit/review/test_hashing.py`, `test_reviewable_facts.py`; `tests/integration/test_review_staleness.py`.

## Progress log
- 2026-10-24: built. Unit 34 (review) + workpapers pass; `test_review_staleness.py` 1 pass. Trial-balance and mapping-set digests are text joins, not JSON, and are left as they are (DEC-215): moving them now would mark every signed trial balance stale. Their owner rows move them to the helper with a recorded re-sign.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-215 | Number and decimal rules, the workpaper switch, trial balance and mapping digests left as they are | No (ADR-160) |
