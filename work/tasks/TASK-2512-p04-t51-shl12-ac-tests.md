---
id: TASK-2512
title: P-04-T51 independent acceptance tests for the SHL-12 UI
spec: SPEC-000
acceptance_criteria: [AC-1]
risk_zone: amber
status: done
epic: P-04
plan_key: P-04-T51
branch: s20-p04-t51
created: 2026-10-30
updated: 2026-10-30
---

## Objective
[AC-1] "Tests written pass and fail if a stale sign-off can be kept or a denied level offered."
(ADR-078; written from the P-04 spec and the C3 contract.)

## Plan (amber)
- `apps/web/src/screens/SHL-12/SHL-12.ac.test.tsx`:
  - the picker offers exactly `levels_allowed` (a, g) and no denied level;
  - b, c, d, h: one disabled CTA described by the failing check's words; a click sends nothing;
  - e: Re-sign is the only signing control; no keep/confirm-unchanged control; "Changed after
    sign-off" shown;
  - a: no write until the click; one click, one write;
  - f: a result in words for every bulk item; signed/excluded counts match the server's answer.
- Rollback: delete the file.

## Progress log
- 2026-10-30: written (run at the end review). Lane B complete.
