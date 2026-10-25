---
id: RB-29
title: "Integrity alert: fingerprint, seal or audit hash chain mismatch (SEV1)"
owner: builder
alarms: [audit-chain-mismatch, drill-failure]
last_rehearsed: never
rehearse_by: 2026-12-11
---
# RB-29 · Integrity alert: fingerprint, seal or audit hash chain mismatch (SEV1)

| Field | Value |
|---|---|
| Owner | builder |
| Severity range | SEV1 |
| Linked from | the audit chain mismatch alarm, a failed restore drill, a storage `IntegrityError` |
| SLO affected | none |
| Kill switches that apply | read-only mode (Q-01-T37, not built yet) |
| Rehearse by | R1 (Fri Dec 11, 2026) |
| Last rehearsed | never |
| Last reviewed against an incident | never |

Evidence is immutable and content-addressed; every read checks the tenant binding, the envelope and the SHA-256 fingerprint (`IntegrityError` otherwise). Each firm's audit events are sealed into hash-chained checkpoints (Q-02-T21). A mismatch means something changed what must not change.

## 1. Recognise it
- `make audit-chain-verify TENANT=<uuid>` names checkpoints that no longer match; the nightly verifier alarms.
- An evidence read fails with `IntegrityError` ("stored content does not match its fingerprint").
- A drill reports evidence or sequence mismatches (RB-15).

## 2. Contain
Treat as SEV1 until explained. Stop writes for the firm if the cause may be ongoing (read-only mode once Q-01-T37 lands; until then roll back a suspect release, RB-01). Do not "repair" the row or object.

## 3. Preserve
The checkpoint numbers, the object key and version id, S3 object versions and Object Lock retention for the object, CloudTrail for the bucket and the key. Never content.

## 4. Assess
Storage fault (a missing object version: replication or lifecycle), a bug (a code path that writes where it must not), or tampering (CloudTrail shows a bypass of governance retention: only `abacus-retention-override` can).

## 5. Notify
If a firm's records may be altered or lost: RB-27's 72-hour clock.

## 6. Recover
Restore the object version from the replica bucket (it is the same version id) or the database rows from a restore (RB-10); re-run the verifier.

## 7. Verify
`make audit-chain-verify` passes for the firm; the evidence opens; a drill passes.

## 8. Review
Mandatory.

## Rehearsal log
| Date | Kind (drill, staging walk-through, tabletop) | Result | Changes made |
|---|---|---|---|
