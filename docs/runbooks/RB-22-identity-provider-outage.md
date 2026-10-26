---
id: RB-22
title: "Identity provider outage: break-glass admin sign-in"
owner: builder
alarms: [sign-in-failure-rate]
last_rehearsed: never
rehearse_by: 2026-12-11
---
# RB-22 · Identity provider outage: break-glass admin sign-in

| Field | Value |
|---|---|
| Owner | builder |
| Severity range | SEV2 to SEV1 |
| Linked from | the sign-in failure rate |
| SLO affected | SLO-01 (sign-in errors) |
| Kill switches that apply | none |
| Rehearse by | R1 (rehearsed before Fri Dec 11) |
| Last rehearsed | never |
| Last reviewed against an incident | never |

Staff sign in through hosted WorkOS AuthKit (P-54; the identity adapter port); the portal uses its own code sign-in (P-08). Sessions already issued keep working until they expire.

The portal half: a client locked out of sign-in or two-step is RB-35; pausing one firm's portal sign-in is RB-36 (P-08-T28).

## 1. Recognise it
New staff sign-ins fail at the WorkOS step; WorkOS's status page reports an incident; the deploy smoke's sign-in step fails.

## 2. Contain
Tell signed-in staff not to sign out. Nothing in the platform can mint a WorkOS session.

## 3. Preserve
Error rates on the sign-in callback and the WorkOS incident reference.

## 4. Assess
How many firms are blocked and for how long; whether a deadline is affected. The portal is not affected unless P-08's sender is.

## 5. Notify
Status page, "Accrued app", SEV2 template.

## 6. Recover
1. Wait for WorkOS while the outage is short.
2. A break-glass staff sign-in path for a firm admin who must act during a long outage is P-01's (session BFF, P-01-T09); until it exists there is none, and this runbook records the gap. Never create a local password account in production.

## 7. Verify
A staff sign-in through AuthKit succeeds on staging and production; the smoke's sign-in step passes.

## 8. Review
Rehearse this runbook before Fri Dec 11 (Q-01-T40) and again once P-01's break-glass path exists.

## Rehearsal log
| Date | Kind (drill, staging walk-through, tabletop) | Result | Changes made |
|---|---|---|---|
