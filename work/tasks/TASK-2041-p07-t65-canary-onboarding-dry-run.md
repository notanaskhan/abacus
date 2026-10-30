---
id: TASK-2041
title: P-07-T65 Onboarding dry run on the canary tenant
spec: SPEC-321
acceptance_criteria: [AC-32]
risk_zone: amber
status: blocked
epic: P-07
plan_key: P-07-T65
branch: s15c-p07-t65
created: 2026-10-30
updated: 2026-10-30
---

## Objective
Synthetic CCH export imported, contacts invited through the fake mail path, acceptance and
independence walked, onboarding kit recorded for M8 and M9; the dry-run record shows every step
completed on the canary before Fri May 28, 2027.

## Built
`docs/ops/rehearsals/canary-onboarding-dry-run.md`: inputs (the committed fictional CCH export,
212 rows), the eight steps with screen states, who, and evidence (CLI-06 g, CLI-04 c, portal sign-in,
CLI-07, CLI-08, the kit's timings), the attribution rule, the run log. SPEC-321 AC-32. Docs only.

## Blocked on
The production compute stack and the canary tenant. P-07 cannot close (its DoD needs this run and
T63's remaining locks).

## Progress log
- 2026-10-30: the dry-run record and AC written; the run waits on production.
