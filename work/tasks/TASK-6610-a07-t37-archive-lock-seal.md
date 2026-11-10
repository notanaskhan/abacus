---
id: TASK-6610
title: "A-07-T37: ArchiveLockWorkflow and seal: human lock decision, snapshot, Merkle root, canonical manifest in COMPLIANCE mode, GOVERNANCE extension, G9, engagement archived"
spec: SPEC-644
acceptance_criteria: [AC-37]
risk_zone: red
status: in-review
branch: s34-a07-t37
worktree: /Users/ayushkbhatia/Accrued/abacus-s34
created: 2026-11-10
updated: 2026-11-10
plan_key: A-07-T37
---

## Objective
Locking Northwind on Dec 3, 2026 yields a seal whose recomputation is byte-identical, a records
object retained in COMPLIANCE mode to Oct 9, 2031, and evidence retained to Oct 9, 2033.

## Plan (red)
1. `assurance/archive_seal.py` (new, pure): leaves (evidence SHA-256s, the reviewables' content
   hashes as the row export, run records' `record_sha256`), Merkle root, RFC 8785-style canonical
   manifest whose SHA-256 is the seal; the audit checkpoint in it.
2. `assurance/archive_lock.py` (new): `decide_lock` (9 of 9, the seen checklist hash, one
   `archive_lock_decisions` row, archive `locking`, audited), `ArchiveLockWorkflow` (batch): seal
   (manifest row v1, `put_record` COMPLIANCE to release + 5 years), extend evidence GOVERNANCE to
   `retention_until`, finish (archive `locked`, `archive.locked` outbox and audit, G9 derives the
   phase, then the engagement and its work items archived). Idempotent per activity.
3. Routes: `POST /archive/lock` (202, idempotent) and `GET /archive/manifest` live.
4. Helpers: `evidence.api.engagement_version_leaves`, `extend_versions_until`;
   `agents.api.run_record_hashes`; event `ArchiveLocked`; reviewed audit actions.
5. Tests: `tests/unit/assurance/test_a07t37_seal.py`.
Rollback: revert; no archive locks until the route is called with `audits.archive` on.

## Progress log
- `2026-11-10` — Built; ruff, pyright clean; the app imports. Tests not run (end pass). Partial:
  the lock decision issues no approval grant row (`approval_grant_id` stays null; the workflow
  re-reads the decision row instead); the FIL-01 "Archive (locked binder)" folder and the seal
  verify run (`/archive/verify`, SealVerifyWorkflow, RB-29) are not built; the replay history
  `archive-lock-v1.json` is recorded at the end pass. The interim SPEC-314 `completion.lock_archive`
  (engagement-level v1) is untouched.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-3207 | Seal leaves, order of the lock steps, no grant row | no |
