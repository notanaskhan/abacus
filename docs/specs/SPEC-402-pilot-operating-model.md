---
id: SPEC-402
title: Pilot operating model and support desk (Q-04 group G)
status: draft
owner: ayushkbhatia
risk_zone: green
related_adrs: [ADR-097]
related_specs: []
created: 2026-10-28
updated: 2026-10-28
---

> **Instructions for coding agents**
> - Documentation only. Q-04's own SPEC, when written, supersedes this one and keeps its AC.

## 1. Summary
`docs/ops/pilot/README.md`: owners, service levels, the shared inbox and its labels, office hours,
pilot codes and the W-signal thresholds, for every pilot window from PW1 (Q-04 §3.7).

## 3. Actors
| Actor | Role in this feature |
|---|---|
| AY | Partner-facing owner, inbox, SEV3 |
| N | SEV1/2 on-call primary |

## 5. Acceptance criteria
- **AC-1** The README names AY as partner-facing owner and N as SEV1/2 on-call with a named backup
  per window; the SLA is first response in 2 business hours in season and SEV1 24x7, matching the
  founding-partner agreement word for word; inbox labels are screen ID, pilot code and severity
  with no client data; office hours Tue/Thu; pilot codes with names only in the vault; W1–W10
  thresholds linked (Q-04 AC-7.1 to AC-7.3, AC-7.5).
