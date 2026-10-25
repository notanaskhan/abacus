---
id: RB-09
title: Key compromise and rotation
owner: builder
alarms: []
last_rehearsed: never
rehearse_by: 2026-12-11
---
# RB-09 · Key compromise and rotation

| Field | Value |
|---|---|
| Owner | builder |
| Severity range | SEV2 to SEV1 |
| Linked from | none yet |
| SLO affected | none |
| Kill switches that apply | none |
| Rehearse by | R1 (Fri Dec 11, 2026) |
| Last rehearsed | never |
| Last reviewed against an incident | never |

Keys: per-tenant KMS multi-Region keys (`alias/abacus/tenant/<tenant>`, P-65; deletion and policy changes only by `abacus-key-custodian`, dual control, ADR-035), the platform KMS keys, the Temporal payload keyring (Secrets Manager `abacus/<env>/temporal/payload-keyring`: several key ids, one current, SPEC-050 AC-14), WorkOS API keys, the Sentry DSN, the email suppression and TIN peppers.

## 1. Recognise it
A secret appears where it should not (a log, a repository, a ticket), a KMS key policy changes unexpectedly (CloudTrail alarm), or a scheduled rotation is due.

## 2. Contain
- **Payload keyring:** add a new key id, make it current; keep the old id until no open workflow history uses it (removing a key still in use is refused). Redeploy workers so they load the new current id.
- **WorkOS or Sentry keys:** rotate in the vendor console, update Secrets Manager, force a new deployment of the API and workers.
- **A tenant KMS key:** disable is denied to everyone but the custodian; the custodian (break-glass, RB-12) disables it, which stops that firm's evidence opening: SEV1 for that firm, so decide with RB-08's questions first.
- A secret committed to git: rotate first, then remove it from the tree (history rewriting is never done on `main`; the rotation is the fix).

## 3. Preserve
CloudTrail for the key or secret (who, when), the leak's location (path, not the secret).

## 4. Assess
What the key protects, since when it may be exposed, whether it was used.

## 5. Notify
If tenant data may be exposed, RB-27's clock applies.

## 6. Recover
Confirm the new keys are in use (workers decode new payloads; sealing uses the new data keys); schedule the old key's removal for after the last history using it closes.

## 7. Verify
A canary run passes end to end on the new keys; replay tests still pass (ADR-090).

## 8. Review
Typical actions: a secrets-scan pattern, a narrower log field, a rotation calendar entry.

## Rehearsal log
| Date | Kind (drill, staging walk-through, tabletop) | Result | Changes made |
|---|---|---|---|
