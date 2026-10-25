---
id: TASK-1217
title: ENG-03 remaining types — step shapes, e consent gate (fixture-only), g group toggle, h SOC 2 (P-07-T34)
spec: SPEC-321
acceptance_criteria: [AC-18, AC-19]
risk_zone: green
status: done
epic: P-07
plan_key: P-07-T34
branch: s8b-eng-ui
created: 2026-10-25
updated: 2026-10-25
---

## Objective
"Scenarios e, g and h render in fixture builds and a firm without the attest entitlement cannot select SOC cards." (P-07-T34)

## Progress log
- 2026-10-25: built on the T21 core. The steps follow the catalogue's step schema (fixture catalogue now carries `steps` as the server serves them); tax "Return setup"; planned CAS close plan and approver row; planned Set up with AI and proposal; Group audit toggle behind `group_audit`; e (Ferris; consents card fixture-only through a gallery-only prop; duplicate notice from Create's 409), g (Harlow & Pike), h (Tessellate SOC 2) scenarios; 8 new ENG-03 tests (19 in the file). No backend change.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-345 | Step shapes, the fixture-only consents card, the duplicate notice at Create, planned controls | No |
