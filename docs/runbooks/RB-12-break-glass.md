---
id: RB-12
title: Break-glass access
owner: builder
alarms: [break-glass-assumed]
last_rehearsed: never
rehearse_by: 2026-12-11
---
# RB-12 · Break-glass access

| Field | Value |
|---|---|
| Owner | builder |
| Severity range | SEV3 to SEV2 |
| Linked from | the break-glass assumption alarm (CloudTrail to EventBridge, pages within 5 minutes) |
| SLO affected | none |
| Kill switches that apply | none |
| Rehearse by | R1 (Fri Dec 11, 2026) |
| Last rehearsed | never |
| Last reviewed against an incident | never |

No standing human access to production data (ADR-028). Elevated access is a time-boxed Identity Center assignment: `BreakGlassAdmin`, `abacus-retention-override`, `abacus-key-custodian`, each for 4 hours or less, alarmed when assumed (SPEC-050 AC-3). Firm-content support sessions are separate: a firm admin approves a scoped, time-boxed session (SPEC-012; the identity module's support sessions).

## 1. Recognise it
- You need it: an incident needs a database console, a retention override or a key custodian action.
- Or the alarm fires and you did not assume it: treat as SEV1 (RB-08, RB-09).

## 2. Contain
Assign the permission set to yourself for the shortest window that covers the task (4 hours at most), with the ticket in the reason. Database access is SSM port forwarding to the instance, never a public endpoint.

## 3. Preserve
The alarm's event, the assignment record, and a short log of every command you run (the session's CloudTrail is the record; your notes link to it).

## 4. Assess
Is there a less privileged way (an ops task, an ops request)? Use it if so.

## 5. Notify
Nobody outside for routine use; the incident's review lists the session.

## 6. Recover
Remove the assignment as soon as the task is done; do not wait for expiry.

## 7. Verify
The assignment is gone (Identity Center), and CloudTrail shows no further use.

## 8. Review
Every use gets a line in the incident review: why the ops-task path was not enough.

## Rehearsal log
| Date | Kind (drill, staging walk-through, tabletop) | Result | Changes made |
|---|---|---|---|
