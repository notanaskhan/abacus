---
id: TASK-1712
title: Q-04-T015 Onboarding kit v1 (docs/runbooks/pilot-onboarding.md)
spec: SPEC-402
acceptance_criteria: [AC-2]
risk_zone: amber
status: in-review
epic: Q-04
plan_key: Q-04-T015
branch: s14-q04-t015
created: 2026-10-28
updated: 2026-10-28
---

## Objective
The pilot onboarding kit: how a pilot firm goes from no tenant to ready for `LEVEL=shadow`, with
the firm loading its own content through its own screens. Acceptance (backlog row): "Every step
names its screen state or CLI, operator and evidence, and no step loads firm content through a
commit or the seed loader."

## Plan (amber, documentation only)
- `docs/runbooks/pilot-onboarding.md` (procedure frontmatter like `demo-tenant.md`; rehearse by
  M8, Fri May 28, 2027): rules; sections 0–12 as tables of step, who, where (handoff screen state
  or CLI), evidence; a "Never" list; a timings table for T016, T018 and the first firm.
- Sources: Q-04 §3.5 (AC-5.1–5.7) and §3.6 (AC-6.1, 6.2); `abacus_tools.tenants` and the Makefile
  (`entitlement`, `agent-stage`); contracts intake-import, email-templates, portal-settings,
  security-center, retention, ai-policy, methodology-programs, notifications; RB-37; the handoff
  READMEs for ADM-02, ADM-03, ADM-04, ADM-06, ADM-10, CLI-06, KNW-01, POR-20, PLT-01.
- Not yet live, named as such in the steps: sending domains (R-01-T27, 501 today), the AI policy
  services (G-02, stub), `make go-live-check` (Q-04 group F), PLT-01 (G-04, S51).
- SPEC-402 gains AC-2. No code, no migration, no flag.
- Rollback: revert the branch.

## Acceptance
| Check | Where |
|---|---|
| Every step has who, where and evidence | `docs/runbooks/pilot-onboarding.md` §§0–12 |
| No step loads content through a commit or the seed loader; the seed loader is named as refusing pilot firms | Rules 1–3 and "Never" |
| Frontmatter valid | `python -m abacus_tools.quality.validate_docs` |

## Progress log
- `2026-10-28` — Written; validate_docs clean. Branch is off #534 (SPEC-402) with origin/main
  merged for RB-37 and the contracts it cites.

## Handoff
- **Current state:** PR open, held for the S14 batch (on #534).
- **Next:** Q-04-T016 and T018 rehearse it on staging and fill in the timings.
