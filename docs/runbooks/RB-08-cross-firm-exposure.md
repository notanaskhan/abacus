---
id: RB-08
title: Suspected cross-firm exposure (SEV1)
owner: builder
alarms: [isolation-alarm, audit-chain-mismatch]
last_rehearsed: never
rehearse_by: 2026-12-11
---
# RB-08 · Suspected cross-firm exposure (SEV1)

| Field | Value |
|---|---|
| Owner | builder |
| Severity range | SEV1 |
| Linked from | isolation and audit alarms; a report from a firm or a tester |
| SLO affected | all |
| Kill switches that apply | read-only mode per platform or firm (Q-01-T37, not built yet); per-firm agent pause; rollback (RB-01) |
| Rehearse by | R1 (tabletop, M4-08) |
| Last rehearsed | never |
| Last reviewed against an incident | never |

INV-3 and INV-4: walls hold and portal scopes stay isolated; every query is tenant-scoped (ADR-014). A suspected crossing is SEV1 until shown otherwise.

## 1. Recognise it
- A person sees another firm's or another client's record; a tester's finding; an isolation test failing on `main`; the audit hash chain or an access-event check flags reads across firms (RB-29).
- Get the exact request: time, route, the two tenant UUIDs, the user. Never ask for a screenshot of client content in a ticket.

## 2. Contain
1. Stop the path: roll back the last release if it introduced the route (RB-01). Until read-only mode exists (Q-01-T37), pausing writes means a release that disables the route.
2. Revoke the affected session (support sessions: RB-12; staff sessions through the session service).
3. Do not delete anything: evidence is immutable and the trail is the proof.

## 3. Preserve
Freeze the window: CloudWatch logs (request ids only), `access_events` and `audit_events` rows for both tenants (as the database owner, read-only, under break-glass with a recorded reason, RB-12), the release record. Store them in the incident's restricted folder (vault reference), never in a ticket.

## 4. Assess
Which data classes were shown (ADR-031: Restricted, tax return information, personal identifiers), how many records, which firms and clients, the window, whether it was read or written.

## 5. Notify
RB-27 sets the 72-hour clock for each affected firm; use the counsel-approved notice (vault reference). Status page only with the SEV1 template, naming no firm or client.

## 6. Recover
Fix with a test that reproduces the crossing first (isolation suite), then the code; ship as a security fix (CLAUDE.md working agreement 1).

## 7. Verify
The reproducing test passes; the isolation and backfill suites pass; access events show no further crossing.

## 8. Review
Mandatory written review; every action becomes a test, a lint rule or an ADR.

## Rehearsal log
| Date | Kind (drill, staging walk-through, tabletop) | Result | Changes made |
|---|---|---|---|
