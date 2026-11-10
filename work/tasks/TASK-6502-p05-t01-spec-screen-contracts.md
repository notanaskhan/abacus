---
id: TASK-6502
title: "P-05-T01: gate check, SPEC-650 and screen contracts SHL-17, SHL-18, AUD-29"
spec: SPEC-650
acceptance_criteria: [AC-1]  # SPEC with numbered ACs and three screen contracts; gate recorded
risk_zone: green
status: in-review
branch: s33-p05-t01
worktree: /Users/ayushkbhatia/Accrued/abacus-s33
created: 2026-11-09
updated: 2026-11-09
plan_key: P-05-T01
---

## Objective
P-05's SPEC and screen contracts, with the gate check and the P-29 dark-merge reading recorded.

## Plan
1. [x] Gate check against main 7c00ad484 (SPEC-650 §2).
2. [x] SPEC-650 with AC-1 to AC-39 transcribed verbatim from P-05 §3.
3. [x] `docs/screens/SHL-17.md`, `SHL-18.md`, `AUD-29.md` from the handoff READMEs and P-05 §4.3, §5.
4. [x] Decide OQ-1 to OQ-9 with the plan's recommended answers (DEC-3102).

## Progress log
- `2026-11-09` — Done, partly: the row's "ADR-209 (P-42) is Accepted on origin/main" is not met
  (ADR-236 is proposed; acceptance is Ayush's, DEC-3101). The P-29 reading is recorded in SPEC-650 §2
  instead of minuted at a Contract Monday (solo edition). SHL-17c's viewer is marcus-delaney (the
  handoff README says Margaret; the artboard is "Assigned to me").

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-3102 | P-05 gate, the P-29 dark-merge reading and OQ-1 to OQ-9 | no |
