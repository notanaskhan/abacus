---
id: TASK-2036
title: Q-04-T021 M9 dossiers per PW1 firm, part N
spec: SPEC-402
acceptance_criteria: [AC-6]
risk_zone: amber
status: blocked
epic: Q-04
plan_key: Q-04-T021
branch: s15c-q04-t021
created: 2026-10-30
updated: 2026-10-30
---

## Objective
Tenant, identity, operations and data-protection sections of `docs/ops/go-live/<pilot-code>.md`
with `make go-live-check LEVEL=shadow` output (F-09 fills contract and legal); each PW1 dossier
shows every chapter 06 §8.3 item green with evidence and is signed by both founders by Fri May 28.

## Plan (amber: written before the code)
- `abacus_tools.go_live_dossier`: `new` (from the template), `fill` (the go-live check's JSON into
  each section's generated block; `communications.*` checks move to Communications), `check`
  (check-fast: pilot code, no contacts, every section) and `check --ready` (the acceptance: a
  passing check within 7 days, every by-hand row green, the shadow rules acknowledged).
- `docs/ops/go-live/_TEMPLATE.md` generated from the tool (a test keeps them equal).
- The sections carry §8.3 by owner: N (tenant and identity, data protection, AI, operations), AY
  (communications, content, integrations; T022), F-09 (contract and legal).
- SPEC-402 AC-6; `pilot-onboarding.md` §0.1 names `new`; tests
  `backend/tests/unit/tools/test_go_live_dossier.py` (run at the end review).

## Blocked on
No PW1 firm has a pilot code assigned or a production tenant (F-09 signs the firms; the production
stack is not provisioned), so no dossier exists yet and none can be filled or signed.

## Progress log
- 2026-10-30: tool, template, check-fast entry, AC and tests built.
