---
id: RB-13
title: Firm offboarding and crypto-shred
owner: builder
owning_epic: Q-02
alarms: []
last_rehearsed: never
rehearse_by: 2027-04-16
---
# RB-13 · Firm offboarding and crypto-shred

| Field | Value |
|---|---|
| Owner | builder (written by Q-02) |
| Severity range | SEV3 |
| Linked from | none |
| SLO affected | none |
| Kill switches that apply | none |
| Rehearse by | R2 (on the canary) |
| Last rehearsed | never |
| Last reviewed against an incident | never |

A stub assigned to Q-02; Q-01 only reserved the number and the header (Q-01-T40). The owning epic writes sections 1 to 8 from the template in `docs/runbooks/README.md` before R2.

## 1. Recognise it
To write (Q-02).

## 2. Contain
To write (Q-02).

## 3. Preserve
To write (Q-02).

## 4. Assess
To write (Q-02).

## 5. Notify
To write (Q-02).

## 6. Recover
To write (Q-02).

## 7. Verify
To write (Q-02).

## 8. Review
To write (Q-02).

## Module steps recorded by their epics
The sections above are Q-02's to write. Owning epics record the step their data needs here, in
the order the offboarding runs them:

- **Search index (P-02-T14, C15).** After the firm's records are shredded or exported, and before
  the tenant is closed: `python -m abacus_tools.search purge <tenant>` deletes every
  `search_documents` row and every `search_recents` row of the firm. The index holds metadata only
  and is rebuildable, so nothing in it is retained or exported; verify with the drift check
  answering no rows for the tenant. `membership.deactivated` already purges each person's recents
  as people leave.

## Rehearsal log
| Date | Kind (drill, staging walk-through, tabletop) | Result | Changes made |
|---|---|---|---|
