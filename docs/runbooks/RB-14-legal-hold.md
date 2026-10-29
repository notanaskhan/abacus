---
id: RB-14
title: "Legal hold: apply, release, failures"
owner: builder
owning_epic: Q-02
alarms: [legal-hold-workflow-failure]
last_rehearsed: never
rehearse_by: 2027-04-16
---
# RB-14 · Legal hold: apply, release, failures

| Field | Value |
|---|---|
| Owner | builder (written by Q-02) |
| Severity range | SEV3 to SEV2 |
| Linked from | the hold workflow failure |
| SLO affected | none |
| Kill switches that apply | none |
| Rehearse by | R2 |
| Last rehearsed | never |
| Last reviewed against an incident | never |

A legal hold freezes a client's evidence (all of it, or one engagement or work item) against deletion: each version in scope gets an S3 Object Lock legal hold, and new versions inherit it. `legal_hold.placed` starts `LegalHoldApply` (`legal_hold_apply:<tenant>:<hold>`, batch class), which counts the versions, sets the S3 hold in batches and moves the hold `applying` → `active` (`legal_hold.activated`). `legal_hold.lifted` starts `LegalHoldRelease`, which clears the S3 hold only where no other hold names the object and moves `releasing` → `released`. New versions inherit open holds through the `evidence_version.created` consumer. Q-02-T29; written by Q-02-T51.

## 1. Recognise it
- A hold stays `applying` or `releasing` for more than an hour (the hold list on G-02's legal-hold screen, or `legal_holds.status`).
- The workflow failure alarm (`legal-hold-workflow-failure`): `LegalHoldApply` or `LegalHoldRelease` failed in Temporal (workflow id names the tenant and hold).
- A new version's inheritance failed: the `evidence_version.created` consumer's error in the relay log (`outbox.publish_failed`, event type `evidence_version.created`).

## 2. Contain
- **Apply failing:** nothing is deleted while the hold is `applying`: retention and erase already treat `applying` as open (`OPEN`), so content is protected even before every object carries the S3 hold. Do not lift the hold to "retry".
- **Release failing:** the objects stay held, which is the safe side. Tell the firm's admin the release is delayed.
- **Hold check slot missing:** retention and erase fail closed while no hold check is registered; that is by design.

## 3. Preserve
Keep the Temporal history of the failed run (its id) and the relay error; no object, file name or client name in tickets.

## 4. Assess
1. Read the run's failure: an S3 `AccessDenied` or throttling (IAM or KMS change, Object Lock not enabled on the bucket), a database error, or a timeout on a large scope.
2. For inheritance, find the version id and whether its hold was counted in its own transaction.

## 5. Notify
The firm's admin and the person who placed or lifted the hold, in identifiers only (hold id, scope kind, counts). A hold failing in a way that put content at risk of deletion is a SEV2 and RB-27 does not apply (no data left Accrued).

## 6. Recover
1. Fix the cause (IAM or bucket policy through Terraform; never by hand in production).
2. Restart the run with the same workflow id: the workflow is idempotent per hold, counts again and sets only what is missing; a redelivered `legal_hold.placed` attaches to the running one.
3. Inheritance: the relay retries the event with back-off; once the cause is fixed it succeeds on its own. An event parked after its maximum attempts is a queue problem: follow RB-06 for that one event id.

## 7. Verify
The hold reads `active` (or `released`); its object count equals the versions in scope; a spot check of three objects shows the S3 legal hold `ON` (or `OFF` after release, unless another hold names them); the audit trail has `legal_hold.activated` or `legal_hold.released`.

## 8. Review
Blameless review linking this runbook. If a scope was too large for one activity timeout, record its size and lower the batch.

## Rehearsal log
| Date | Kind (drill, staging walk-through, tabletop) | Result | Changes made |
|---|---|---|---|
