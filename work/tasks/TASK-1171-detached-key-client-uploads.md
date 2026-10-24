---
id: TASK-1171
title: Detached-key storage for client-channel uploads - envelope v2, evidence_object_keys, migration 0144, key retained on acceptance (P-06-T18)
spec: SPEC-319
acceptance_criteria: [AC-15]
risk_zone: red
status: done
epic: P-06
plan_key: P-06-T18
branch: s7c-client-uploads
created: 2026-10-24
updated: 2026-10-24
---

## Objective
"A client upload opens only through its key row and firm uploads keep the content-addressed path unchanged." ADR-162 §5 (the plan's "ADR-137"; the number was minted for the module map, so P-31 is ADR-162).

## Plan (red zone)
- **Kernel:** `kernel/crypto` envelope v2 (`seal_detached`, `seal_under`, `open_detached`, `DetachedKey`).
- **Evidence:** `storage.put_detached`, `storage.put(..., under=)`, `storage.get` for detached paths, `KeyDestroyed`; `object_keys.py` (`key_for`, `under_key`); `models.py` (`storage_mode`, `EvidenceObjectKey`, `EvidenceWithdrawal`); `repository.insert_object_key`; `service.add_version(detached=)`; `uploads.upload` stores a client's own upload detached; `processing.py` and `words.py` seal derived records under the version's key.
- **Migration 0144** (`down_revision` 0143): `evidence_versions.storage_mode` and the per-mode key CHECK; `evidence_object_keys` with its guard; `evidence_withdrawals` with insert and stamp guards (used by T19); `review_decisions_retain_key`; `evidence_key_destroy` (definer). Rollback: `alembic downgrade 0143` (refused while a detached-key version exists).
- **Registries:** `evidence/registry.py` tables and columns; `schema_check.DEFINER_FUNCTIONS` with `test_schema_check_db.py`.
- **Tests:** `tests/unit/kernel/test_crypto_detached.py`; `tests/integration/backfill/test_p06t18_detached_keys.py` (6).

## Progress log
- 2026-10-24: built. The local S3 (POSIX-backed) refuses an object key that is also a prefix, so derived objects live in a sibling `vd/` tree (DEC-297). 0007's `evidence_versions_key_is_content_address` CHECK is redefined per storage mode. Not done here: deleting a withdrawn version's derived database rows (`upload_extractions` etc. are insert-only; the purge's erase makes their objects unreadable, which is what ADR-162 §6 needs for content; the rows are identifiers and code-computed fields). That is T19's purge scope.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-297 | Which uploads are detached, envelope v2, paths, retention trigger | No (ADR-162) |
