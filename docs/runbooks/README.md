# Runbooks (ADR-098)

One runbook per failure scenario, written so the builder can follow it half-awake with nothing else open. This README is the index and the template. The scenario list comes from ADR-098 (RB-01 to RB-16) and chapter 06 §3.7 (RB-17 to RB-30).

## Rules

1. **Every alert links a runbook.** An alert definition without a runbook link is rejected (ADR-098). A runbook with no alert says so in its header.
2. **Every runbook is rehearsed** at least once by its `rehearse by` date, and records the date. A drill, a staging walk-through or a tabletop all count; reading it does not.
3. **Stale runbooks raise a ticket.** A runbook is stale when its `rehearse by` date has passed without a rehearsal, or when its last rehearsal is over 12 months old. The 12-month figure is this file's default because ADR-098 sets none; change it with a dated line here.
4. **Each incident ends with a blameless written review** whose actions become tests, lint rules, alerts or ADRs (ADR-097). The review links the runbook it exercised and updates it.
5. Runbooks hold procedure, not secrets. Never put account IDs, keys, recovery codes, customer names, counsel-drafted notification text or contact numbers in git. Point to the vault by opaque reference (for example `V-031`).
6. Severity and kill switches are defined in ADR-097: SEV1 is suspected cross-firm exposure or a full outage in busy season; SEV2 a major feature or provider outage; SEV3 degraded service or one firm.

File name: `RB-<nn>-<slug>.md`, for example `RB-08-cross-firm-exposure.md`. Each runbook starts with frontmatter that `validate_docs` checks (Q-01-T21): `id`, `title`, `owner`, `alarms` (a list; empty when no alarm links it) and `last_rehearsed` (an ISO date or `never`), plus `rehearse_by`. Every alarm resource in `infra/` names its runbook (`RB-<nn>` in its description or a `runbook` tag) and that runbook must exist, or `validate_docs` fails.

## Gate dates used below

| Level | Date |
|---|---|
| R0 (production-shaped staging) | Fri Nov 13, 2026 |
| R1 (production with the canary) | Fri Dec 11, 2026 |
| R2 (real-data gate, M7) | Fri Apr 16, 2027 |
| R3 (client-facing pilot) | Tue Jul 13, 2027 |

## Index

Owner is the builder for every row. `Last rehearsed` stays `never` until a rehearsal is recorded in the runbook. `State` is `to write`, `stub` (the number and header reserved; the owning epic writes it), `drafted`, or `rehearsed`.

| ID | Scenario | Source | Rehearse by | Last rehearsed | Alert it is linked from | State |
|---|---|---|---|---|---|---|
| RB-01 | Deploy and rollback | ADR-098 | R0 | never | SLO-01, SLO-10 | drafted |
| RB-02 | Failed migration | ADR-098 | R0 | never | none yet | drafted |
| RB-03 | Model provider outage: throttling or outage on the approved route; degrade and queue, never reroute client data | ADR-098, ADR-072, ADR-113 | R1 | never | SLO-04 | drafted |
| RB-04 | Connector provider outage | ADR-098 | First live connector | never | SLO-08, SLO-09 | stub (A-02 writes it) |
| RB-05 | Expiring-connections wave (reconnect requests to clients) | ADR-098 | First live connector | never | SLO-09 | stub (A-02 writes it) |
| RB-06 | Queue backlog per work class | ADR-098, ADR-071 | R1 | never | SLO-05 | drafted |
| RB-07 | AI cost spike (anomaly job, budgets) | ADR-098, ADR-069 | R1 | never | cost anomaly | drafted |
| RB-08 | **Suspected cross-firm exposure (SEV1)** | ADR-098, ADR-097 | R1 (tabletop, M4-08) | never | audit and isolation alarms | drafted |
| RB-09 | Key compromise and rotation (KMS, payload keyring, workflow and identity keys) | ADR-098, ADR-035 | R1 | never | none yet | drafted |
| RB-10 | Restore from backup | ADR-098, ADR-096 | R1 (drill, M4-05) | never | none (drill) | drafted |
| RB-11 | Regional failover | ADR-098, ADR-096 | R2 (tabletop), then yearly | never | none (tabletop) | drafted |
| RB-12 | Break-glass access: support sessions, retention override, key custodian | ADR-098, ADR-028 | R1 | never | break-glass audit event | drafted |
| RB-13 | Firm offboarding and crypto-shred | ADR-098, ADR-034 | R2 (on the canary) | never | none | stub (Q-02 writes it) |
| RB-14 | Legal hold: apply, release, failures | ADR-098, ADR-033 | R2 | never | hold workflow failure | stub (Q-02 writes it) |
| RB-15 | Disaster-recovery drill procedure | ADR-098, ADR-096 | R1 | never | none (drill) | drafted |
| RB-16 | Busy-season readiness | ADR-098, ADR-075 | Aug 2027 | never | readiness test | stub (Q-04 writes it) |
| RB-17 | Section 7216 consent expiry or revocation wave (agents pause per taxpayer) | R-01 | R2 if tax is in scope | never | consent alarms | to write |
| RB-18 | E-signature or knowledge-based-authentication vendor outage (record mode; wet-signature path) | R-05, ADR-149 | R3 | never | provider health | to write |
| RB-19 | Tax-engine bridge failure near a filing deadline (file fallback) | P-18 | Aug 2027 | never | bridge failure | to write |
| RB-20 | Email deliverability incident (bounce or complaint spike; a firm's sender authentication breaks) | P-11 | R1 | never | SLO-07 | drafted |
| RB-21 | Portal custom domain or certificate failure | P-11 | R3 | never | certificate expiry | to write |
| RB-22 | Identity provider outage: break-glass admin sign-in | ADR-029, ADR-141 | R1 | never | sign-in failure rate | drafted |
| RB-23 | Workflow engine outage or worker disconnection | ADR-017 | R1 | never | SLO-05 | drafted |
| RB-24 | Malware scanner down (fail-closed backlog; signature staleness) | ADR-110, ADR-153 | R0 | never | SLO-03 | drafted |
| RB-25 | Provider-terms register entry nearing `review_by` (AI refused for real firms once past) | ADR-114 | R2 | never | register expiry | to write |
| RB-26 | Feature-flag expiry wave (fast check red) | ADR-089 | Dec 2026 | never | flag expiry check | drafted |
| RB-27 | **Accrued-originated incident touching firm data:** notify the firm within 72 hours and create the incident-register entry so the firm's own 30-day clock starts with facts | R-27, R-32 | R2 (tabletop) | never | incident created | to write |
| RB-28 | Real-time delivery degraded (event stream down; clients fall back to polling) | P-15 | When P-15 ships | never | SLO-06 | to write |
| RB-29 | Integrity alert: evidence fingerprint mismatch, seal mismatch, or broken audit hash chain (SEV1) | ADR-096 | R1 | never | chain mismatch alarm | drafted |
| RB-30 | Write-capability incident (wrong posting or export; reversal as a new write) | P-16 | Before the first write capability goes live | never | write anomaly | to write |
| RB-31 | Pause notification email for a firm or every firm (`notifications.email`, the C16 channel's kill switch) | P-01-T17 | R1 | never | none yet (RB-20 points here) | drafted |
| RB-32 | Client withdrawal: erase failures and legal-hold conflicts (`EvidenceWithdrawalPurge`, ADR-162) | P-06-T27 | R2 | never | none yet | drafted |
| RB-34 | Audit label indexer failing, lagging or paused (`AuditLabelIndexer`, `audit_labels:platform`; DEC-453) | G-02-T10 | R1 | never | none yet | drafted |

Also owed by Q-02-T51, not yet numbered: agent stage promotion and demotion; Bedrock route-parity refresh. Give each the next free RB number when written (RB-33 onward; RB-31 is P-01-T17's, RB-32 P-06-T27's).

## Template

Copy into `RB-<nn>-<slug>.md`.

```markdown
---
id: RB-<nn>
title: <scenario>
owner: builder
alarms: [<alert ids>]
last_rehearsed: never
rehearse_by: <YYYY-MM-DD>
---
# RB-<nn> · <scenario>

| Field | Value |
|---|---|
| Owner | builder |
| Severity range | SEV<n> to SEV<n> |
| Linked from | <alert ids or "none yet"> |
| SLO affected | <SLO-nn or none> |
| Kill switches that apply | <platform AI pause / per-firm / per-engagement / connector disable / read-only mode / none> |
| Rehearse by | <date> |
| Last rehearsed | <date or never> |
| Last reviewed against an incident | <incident id or never> |

## 1. Recognise it
What fires, what the dashboard shows, and the two or three checks that confirm this is the scenario and not a neighbour (link RB-<nn>).

## 2. Contain
The first action that limits harm, with the exact command, flag or console path. If real firm data may be exposed, say so and go to RB-08.

## 3. Preserve
What to capture before changing anything: logs, run records, audit rows, snapshots. Where it goes. Never copy client content into a ticket.

## 4. Assess
Questions that decide severity: which firms, which data classes (ADR-031), which window, whether tax return information or personal identifiers are involved.

## 5. Notify
Who must be told, by when, and from which counsel-approved template (vault reference). For incidents touching firm data, RB-27 sets the 72-hour clock.

## 6. Recover
Ordered steps to restore service, with the check that proves each one worked. Include the rollback.

## 7. Verify
How to know it is over: the metric, the canary run, the test.

## 8. Review
Open the blameless review. Each action becomes a test, a lint rule, an alert or an ADR. Update this runbook and set "Last reviewed against an incident".

## Rehearsal log
| Date | Kind (drill, staging walk-through, tabletop) | Result | Changes made |
|---|---|---|---|
```
