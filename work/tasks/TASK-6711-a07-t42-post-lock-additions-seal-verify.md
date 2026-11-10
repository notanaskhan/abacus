---
id: TASK-6711
title: "A-07-T42: post-lock additions (create, EP approve or reject with fresh MFA under archive_addition, addition hash and appended manifest in records) and seal verification (POST verify, monthly SealVerifyWorkflow, RB-29 on mismatch, restore-drill hook)"
spec: SPEC-644
acceptance_criteria: [AC-37]
risk_zone: red
status: in-review
branch: s35-a07-t42
worktree: /Users/ayushkbhatia/Accrued/abacus-s35
created: 2026-11-10
updated: 2026-11-10
plan_key: A-07-T42
---

## Objective
The PI-02 memo is appended on Jan 15, 2027 only after Margaret Okonkwo approves, the original seal is unchanged, and a tampered row makes verify report seal_mismatch.

## Plan (red)
1. `assurance/archive_additions.py` (new): `create_addition` (live person; locked archive; the
   evidence version's fingerprint; description sealed to its addition; the addition manifest's
   canonical bytes hashed into `content_sha256` and its content-addressed records key in
   `addition_manifest_key`, both at creation; insert under `allow_archived_write("archive_addition")`);
   `decide_addition` (never the person who added it; approval rebuilds the manifest byte for byte,
   writes it to `records` in COMPLIANCE mode to the five-year floor, then the human-only decision
   row and `archive.addition_logged`; rejection seals its reason). The original seal is never
   written.
2. Verification: `seal_matches` (the restore-drill hook) rebuilds the leaves with
   `archive_lock.seal_leaves` (refactored out of the seal activity) and compares the Merkle root
   with `archive_manifests` v1, then reads the COMPLIANCE manifest back; `SealVerifyWorkflow` for
   `POST …/archive/verify`, `SealVerifySweepWorkflow` on the monthly Schedule `seal_verify:platform`;
   a mismatch records `archive.seal_mismatch`, counts `abacus.archive.seal_mismatch` and logs the
   RB-29 event (metadata only).
3. Routes in `release_contract.py` implemented (501 stays declared); `GET …/archive` lists the
   additions.
4. Evidence: record class `addition_manifest`; `evidence.api` exports `record_key`,
   `version_fingerprint`.
5. Registry: assurance WORKFLOWS, ACTIVITIES, SCHEDULES; reviewed actions; error codes
   `archive_not_locked`, `addition_already_decided`, `evidence_version_invalid`.
6. Tests: `tests/unit/assurance/test_a07t42_additions_verify.py`.
7. Rollback: revert; locked archives and their seals are untouched by this code.

## Partial
- "Archive and roll forward" → ENG-13 after lock: the lock decision records `then_roll_forward`
  (A-07-T37); the hand-off link is the front end's (A-07-T39 shows it); no server change here.
- A run record packaged after lock would change the run-record leaves; agent runs are exempt from
  the guard, so a run ending after lock could raise a false mismatch. Recorded for the end-pass
  review (the seal's run leaves should be the lock-time set).
- Integration (lock, add, approve, verify on Postgres and MinIO) runs at the end pass.

## Progress log
- `2026-11-10` — Built; tests written, not run (end pass).
