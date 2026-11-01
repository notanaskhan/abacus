---
id: TASK-2637
title: N-02-T46 RB-18 runbook and the four signing screen contracts closed
spec: SPEC-381
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: amber
status: in-review
epic: N-02
plan_key: N-02-T46
branch: s21-n02-t46
worktree: /Users/ayushkbhatia/Accrued/abacus-s21
created: 2026-11-01
updated: 2026-11-01
---

## Objective
RB-18 (e-signature or KBA vendor outage: record mode, the wet-signature path for the e-file
family, client message templates as database content), rehearsed once by notanaskhan; the four
screen contracts closed with their status and Deviations.

## Plan
Docs only: `docs/runbooks/RB-18-esign-vendor-outage.md` rewritten for DocuSeal (ADR-342) from the
N-02-T17 first notes; index row; `docs/screens/{SIG-01,SIG-02,POR-06,ENG-04}.md` status lines and a
Deviations section each (DEC-1679). Rollback: revert.

## Deviations
- The row's dependency N-02-T44 (DocuSeal production enablement) waits on the deferred pen-test
  delta #2 (DEC-1389); the runbook is written against the staging install and the flags as built.
- "Live status": each screen's status names the flip that makes it live; none is live yet.
**Human:** the rehearsal on staging (notanaskhan, PF-X1).

## Progress log
- 2026-11-01: written.
