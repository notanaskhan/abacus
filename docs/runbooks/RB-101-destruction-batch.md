---
id: RB-101
title: "Destruction batch: stuck, partial, wrong batch, replica mismatch, kill switch (Q-05-T29)"
owner: builder
owning_epic: Q-05
alarms: []
last_rehearsed: never
rehearse_by: 2028-12-15
---
# RB-101 · Destruction batch (Q-05-T29; ADR-179; DEC-6044)

**Who:** the on-call engineer and a security admin (two people for any step that deletes).
**Applies to:** Q-05-T15's `DestructionExecuteWorkflow` over an approved destruction batch (FIL-02),
under the destruction role proved by RB-100. Nothing here shortens a retention or lifts a hold.

## Stuck batch
1. FIL-02 shows the batch "Executing" with no item moved in 30 minutes. Open the workflow in
   Temporal (`destruction-execute:<batch>`) and read the last activity's error.
2. A transient S3 or KMS error retries by itself. A permission error means the role lost its
   policy: stop and follow RB-100's check list before resuming.
3. Resume with the workflow's `resume` signal. Items already destroyed are skipped (each is
   recorded once, by key).

## Partial batch
1. The certificate is issued only for destroyed items; the batch reads "Partly destroyed" with the
   count. Each refused item names its reason (held, retain-until in the future, replica pending).
2. Fix the reason at its owner (a hold is lifted only by its owner in RB-14), then re-run the
   batch; it re-checks every item at execution, never trusting the approval's snapshot.

## Wrong batch
1. Set the `destruction_execute` kill switch (below) at once.
2. Items destroyed before the switch cannot be recovered from the primary; check the replica's
   retention window and escalate as a SEV1 with the batch id.
3. Record the incident from `docs/ops/incident-templates.md`; the batch's approvers are named in
   its audit trail.

## Replica mismatch
1. The certificate verifier reports an object present in the replica after its primary was
   destroyed (or the reverse). Do not delete by hand.
2. Wait for the replica's own lifecycle (the cross-region rule); re-run the verifier. A mismatch
   older than the replica's lifecycle is a SEV2.

## Kill switch
- `python -m abacus_tools.platform_control set --control destruction_execute --scope platform
  --on --operator <you> --reason "<why>"` (`--scope firm --tenant <id>` for one firm). The
  workflow checks it between items and stops; the batch reads "Stopped" and keeps its progress.
- Turn it off (`--off`) only after the cause is fixed; resume the batch from FIL-02.

## Quarterly drill (staging, synthetic tenant)
1. Approve a three-item synthetic batch (A expired, B held, C retain-until in the future).
2. Execute; set the kill switch after the first item; check the batch stops between items.
3. Clear the switch; resume; check A is destroyed, B and C are refused with their reasons.
4. Verify the certificate; trigger the out-of-batch alarm with a direct delete attempt by the
   destruction role and check on-call is paged.
5. Record the date in `last_rehearsed` (a person runs the drill; staging is human).
