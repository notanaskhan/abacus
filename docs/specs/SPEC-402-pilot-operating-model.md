---
id: SPEC-402
title: Pilot operating model, support desk and onboarding kit (Q-04 groups E and G)
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
`docs/runbooks/pilot-onboarding.md` (Q-04-T015): the onboarding kit, from provisioning to
`LEVEL=shadow`, with every firm's content loaded through its own screens (Q-04 §3.5).

## 3. Actors
| Actor | Role in this feature |
|---|---|
| AY | Partner-facing owner, inbox, SEV3 |
| N | SEV1/2 on-call primary; runs the operator commands (provision, entitlements, agent stages) |
| Firm admin, security admin, quality partner | Load their firm through its own screens (CLI-06, KNW-01, POR-20, ADM-02, ADM-03, ADM-04, ADM-06, ADM-10) |

## 5. Acceptance criteria
- **AC-1** The README names AY as partner-facing owner and N as SEV1/2 on-call with a named backup
  per window; the SLA is first response in 2 business hours in season and SEV1 24x7, matching the
  founding-partner agreement word for word; inbox labels are screen ID, pilot code and severity
  with no client data; office hours Tue/Thu; pilot codes with names only in the vault; W1–W10
  thresholds linked (Q-04 AC-7.1 to AC-7.3, AC-7.5).
- **AC-2** `docs/runbooks/pilot-onboarding.md` covers provisioning, SSO and MFA, roles and walls,
  bulk client import, PBC templates, email templates and branding, sender domain, retention
  policies, AI opt-in and stages, the support-session switch and status subscribers; every step
  names its screen state or CLI, its operator and its evidence, and no step loads firm content
  through a commit or the seed loader (Q-04-T015; Q-04 AC-5.1 to AC-5.7).
- **AC-7** Each PW1 dossier's AY sections (communications, content, integrations) are green with the
  evidence `docs/ops/pilot/shadow-briefing.md` §3 names, and every firm admin has acknowledged the
  shadow rules (shadow-briefing v1: staff only, no client email, nothing client-facing, agents in
  shadow, the firm's tools the system of record) in writing, recorded in the dossier by date,
  version and vault entry (Q-04-T022).
