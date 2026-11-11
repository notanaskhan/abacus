---
id: audit-release-archive
title: "Audit release and archive (A-07, M16): release failure, stuck lock, seal mismatch, post-lock additions, rollback, shadow, restore drill and the flip"
owner: builder
alarms: []
last_rehearsed: never
rehearse_by: 2028-03-17
---
# Audit release and archive (A-07, M16)

| Field | Value |
|---|---|
| Owner | builder (both founders approve the flip) |
| Severity range | SEV3 (a release or lock waits a day) to SEV1 (a seal mismatch: RB-29) |
| Source | A-07-T51 (TASK-6823); A-07 §4.5, §4.11, §10; SPEC-644; DEC-3415 |
| Flags | `audits.completion`, `audits.letters`, `audits.report_release`, `audits.archive` (per firm, rollout only); firm setting `assurance_release_mode` (`in_app` or `external`) |

## What it covers
- **G8, the release.** The engagement partner releases with a fresh second factor (`report.release`).
  `ReleaseWorkflow` (`release:<tenant>:<work item>:<grant>`) consumes the approval grant, checks
  G5 to G7 again, renders the final report, then records `report_releases` in one unit of work.
- **G9, the lock.** A manager or the partner locks at 9 of 9 with a fresh second factor
  (`archive.lock`). `ArchiveLockWorkflow` (`archive_lock:<tenant>:<work item>`) then seals: the
  manifest goes to `records` in COMPLIANCE mode until release + 5 years, and evidence objects get
  GOVERNANCE retain-until extended to the archive's retention. The archive becomes `locked`.

Released and locked rows are insert-only, and `archived_guard()` keeps a locked engagement read-only.
**No step here edits or deletes them.**

## 1. A release failed
Symptom: AUD-24 shows the refusal, or the run ends `failed`.

1. Read the workflow in Temporal (`release:<tenant>:<work item>:<grant>`) and the audit event
   `report.release_failed` with its reason:
   - `grant_refused`: the grant was used, voided or expired;
   - `render_failed`: C11 failed the final render;
   - `gates_not_met` / `content_changed`: G5 to G7 or the snapshot moved after the dialog.
2. Nothing was recorded. The grant is void and `report_releases` has no row. Confirm both:
   `SELECT count(*) FROM report_releases WHERE work_item_id = :wi` returns 0.
3. Fix the cause:
   - render: RB-43;
   - a gate: the item AUD-24 names.
   Then the partner releases again; a new grant is issued.
4. Never insert a release row by hand. The one-original index and the human-actor CHECK refuse it.

## 2. A lock is stuck (`locking` for more than 10 minutes)
1. `SELECT status, lock_decision_id, manifest_id FROM archives WHERE work_item_id = :wi`:
   `locking` with a decision.
2. In Temporal, find `archive_lock:<tenant>:<work item>`:
   - Running and retrying: read the failing activity (`seal`, `extend_evidence` or `finish`). A
     records-bucket error is RB-10's storage path. An Object Lock refusal is the bucket's
     configuration: never shorten a retention.
   - Terminated or missing: start it again with `assurance.archive_lock.start_lock` for the same
     work item. It is idempotent: `seal` reuses an existing manifest and `finish` returns when
     the archive is already `locked`.
3. The lock decision stays as recorded. It is never re-decided or deleted.

## 3. A seal mismatch (SEV1)
`SealVerifyWorkflow` (on demand) or the monthly `SealVerifySweepWorkflow` records `archive.seal_mismatch`.
This is **RB-29** (integrity alert). Follow it in full, and do not re-seal or unlock anything.
Quote the archive id, the stored `seal_sha256` and the recomputed root in the incident.

## 4. Post-lock additions
1. A person adds the item from AUD-25 d ("+ Add after lock…") with a reason code
   (`archive_addition.create`).
2. Only the engagement partner approves it (`archive_addition.approve`, fresh MFA). It is never
   approved by the person who added it, the agent or the system.
3. Approval writes the addition's manifest to `records` (COMPLIANCE, until the five-year floor)
   before the decision row. The original archive and its seal are unchanged.
4. An addition stuck without a decision is a person's to decide. Remind the partner; never decide
   it for them.

## 5. Rollback (per firm)
1. Turn off `audits.archive`, `audits.report_release` and `audits.letters` for the firm, in that
   order. The routes answer 404 and the screens show the flag-off state.
2. Set `assurance_release_mode = external`. The firm records releases made outside Accrued again
   (`record_release`).
3. **Released and locked records persist.** Their reports stay Final in POR-09 and their archives
   stay locked and read-only. Rollback never deletes, unlocks or re-dates them.
4. Tell the firm's admin in writing which engagements were released or locked in-app.

## 6. Shadow (from Mon Mar 6, 2028)
1. On staging and the canary, pick one Dec-YE engagement on PF-X1 (synthetic, DEC-1530).
2. Walk J03 15 to 19 and J18 5-6 (`apps/web/e2e/journeys`) with every invariant asserted. Record
   the run ids, the release id, the seal and the clocks (Oct 9 → Dec 8 for the demo).
3. Keep the shadow evidence with the flip request (§8).

## 7. Restore drill: recompute a seal
1. Restore the latest backup to a scratch database (RB-10). **Never point at production.**
2. Pick a locked archive and read `archive_manifests.records_object_key` and `manifest_sha256`.
3. Read the manifest body from `records` by that key. Its SHA-256 must equal
   `archives.seal_sha256`, byte for byte.
4. Recompute the Merkle root from the restored rows (`assurance.archive_lock.seal_leaves` and
   `archive_seal.merkle_root`). It must equal the manifest's `merkle_root`.
   `assurance.archive_additions.seal_matches` does both checks.
5. Record the archive id, both hashes and the result in the drill log.

## 8. The flip (Tue Mar 21, 2028, 7 pm CT)
A firm flips only when every item below is in the flip request:
- J03 and J18 journeys pass on staging (step 6's evidence).
- Shadow evidence on one Dec-YE engagement.
- This runbook rehearsed on staging (§1 to §5), and the restore drill (§7) recomputed one seal.
- A-07-T46's delta security test is closed. DEC-1389 defers penetration tests, so the deferral
  is stated, not claimed met.
- Both founders' approvals.

Then turn on, for that firm, `audits.completion`, `audits.letters`, `audits.report_release` and
`audits.archive`, and set `assurance_release_mode = in_app`.

## Rehearsal log
| Date | Where | Sections | Result |
|---|---|---|---|
| — | — | — | not rehearsed (staging not up; S36 wrote the runbook) |
