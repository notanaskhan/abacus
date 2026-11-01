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
- **AC-6** Each PW1 firm's `docs/ops/go-live/<pilot-code>.md` (made by `abacus_tools.go_live_dossier
  new`, from `_TEMPLATE.md`) carries chapter 06 §8.3 by section and owner; `fill` writes the
  `make go-live-check LEVEL=shadow` rows into each section's generated block; `check` (check-fast)
  refuses a dossier not named by a pilot code, holding an email address or phone number, or missing
  a section; `check --ready` passes only with a passing check from the last 7 days, every by-hand row
  green with evidence and the shadow rules acknowledged, before both founders sign (Q-04-T021).
- **AC-5** `docs/ops/on-call.md` names N as SEV1/2 primary and AY as the named backup for every day
  of each live window (PW1: Jun 1 to Jul 12, 2027), quiet hours in writing, each firm's QI contact by
  pilot code and vault entry (never the contact itself), and a test-page record; a test page reaches N
  and escalates to AY after 15 minutes; `abacus_tools.quality.on_call` refuses an uncovered day, a
  backup equal to the primary, or a phone number or email address in the file (Q-04-T020). For
  the autumn window (Sep 1 to Oct 20, 2027) the rota covers every day with N primary and AY the
  named backup, and each `deploy/windows.yaml` deadline week is on double cover: SEV2 pages both at
  once and quiet hours are suspended; the check refuses a deadline-week day on single cover,
  double cover outside one, and rota dates that differ from the release window's (Q-04-T066).
- **AC-4** `docs/runbooks/firm-rollback.md` takes a firm back inside 60 minutes: every flag off in
  one audited unit of work (`make flag … ALL_OFF=1`), an A-01 export per engagement, and each package
  unpacked into a new folder and verified by `abacus_tools.package_check` (both checksum files, nothing
  unlisted, the manifest agreeing, nothing written outside the folder); the canary rehearsal sets the
  runbook's `last_rehearsed` (Q-04-T019).
- **AC-3** The onboarding rehearsal's part AY (`docs/ops/rehearsals/onboarding-content-part-ay.md`)
  takes 200 synthetic clients through CLI-06 g, a PBC template through the KNW-01 importer, POR-20
  templates to published (l) and ADM-10's sender domain from pending DNS to published (d to f),
  each step through its screen with its timing recorded and each defect filed on its owning epic;
  the inputs come from `abacus_tools.synthetic.onboarding_files`, never from a commit (Q-04-T018).
