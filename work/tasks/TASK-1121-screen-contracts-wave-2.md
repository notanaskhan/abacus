---
id: TASK-1121
title: Screen contracts wave 2 - CLI-04, CLI-06, CLI-07, CLI-08, ENG-05, ENG-13 (P-07-T23)
spec: SPEC-332
acceptance_criteria: [AC-2, AC-13, AC-17, AC-24, AC-26]
risk_zone: green
status: done
epic: P-07
plan_key: P-07-T23
branch: s7-p07-contacts
created: 2026-10-24
updated: 2026-10-24
---

## Objective
"Each contract records its deviations with the deciding DEC or DF ID and the link-contract test knows every target" (P-07-T23).

## Plan (green zone)
- `docs/screens/{CLI-04,CLI-06,CLI-07,CLI-08,ENG-05,ENG-13}.md` from `docs/screens/_TEMPLATE.md`, against the handoff (HANDOFF_VERSION 2026-10-21) and P-07 §5.
- Deviations: CLI-04 d "3 incorrect codes" (DF-24); CLI-06 screening recorded by a person (DEC-64), due dates (DF-10) and the intake toggle (OQ-11) planned; CLI-07 human-prepared flags and the pre-screen fixture-only (DEC-64), record states (DF-06); CLI-08 "Declined with a note" (DF-06), reminders sent by a person; ENG-05 G2 on attest clients only (DEC-39, ADR-164); ENG-13 attest carry and template conflicts fixture-only.
- Every link target is a manifest ID in `apps/web/src/routes/manifest/*.ts` (checked: CLI-01/02/07/08, ENG-02/04/06, POR-02, AUD-02/03, INS-05, BND-04, SHL-08/11/22, WB-13, HOME-02/04).

## Progress log
- 2026-10-24: six contracts written; every outbound target checked against the manifest.
