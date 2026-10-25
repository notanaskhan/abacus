---
id: RB-26
title: Feature-flag expiry wave
owner: builder
alarms: [flag-expiry-check]
last_rehearsed: never
rehearse_by: 2026-12-18
---
# RB-26 · Feature-flag expiry wave

| Field | Value |
|---|---|
| Owner | builder |
| Severity range | SEV3 |
| Linked from | the flag expiry check (fast check red) |
| SLO affected | none |
| Kill switches that apply | the flags themselves |
| Rehearse by | Dec 2026 (F-03-T37's renewal bundle) |
| Last rehearsed | never |
| Last reviewed against an incident | never |

Every feature flag carries an expiry (ADR-089); the fast check fails when one passes without a renewal or retirement. Flags expiring together make `make check-fast` red for everyone.

## 1. Recognise it
`make check-fast` (or CI stage 1) fails on the flag expiry rule, naming the flags.

## 2. Contain
Nothing runtime: an expired flag keeps its last state; the check is a build gate.

## 3. Preserve
The list of flags and their owners from `docs/architecture/feature-flags.yaml`.

## 4. Assess
For each flag: retire it (the feature is on everywhere), or renew it with a reason and a new expiry no earlier than 2027-02-01 (`expires` with `override: DEC-137` where the policy needs it).

## 5. Notify
None.

## 6. Recover
One PR with every renewal and retirement in the wave (batch it; CLAUDE.md working agreement 1), then `make regenerate`.

## 7. Verify
`make check-fast` is green.

## 8. Review
Typical action: stagger expiries so waves do not recur.

## Rehearsal log
| Date | Kind (drill, staging walk-through, tabletop) | Result | Changes made |
|---|---|---|---|
