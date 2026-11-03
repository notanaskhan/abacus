---
id: TASK-3230
title: A-04-T30 Independent AC tests for A-04-T07, T18, T19
spec: SPEC-620
acceptance_criteria: [AC-9, AC-13, AC-20, AC-22]
risk_zone: amber
status: in-review
epic: A-04
plan_key: A-04-T30
branch: s26-a04-t30
worktree: /Users/ayushkbhatia/Accrued/abacus-s26
created: 2026-11-03
updated: 2026-11-03
---

# TASK-3230 · A-04-T30 · Independent AC tests for A-04-T07, T18, T19 and EP-only controls

**Epic:** A-04 · **Sprint:** S26 · **Type:** TEST · **Zone:** amber · **Depends on:** A-04-T07, T18, T19, T21 · **Status:** in-review

## Built
- `backend/tests/contracts/a04_planning/test_a04t30_independent.py` (ADR-078): tailoring refuses a mandatory step; the three planning decision kinds are reserved to the engagement partner; card decisions are human-only; G4 is `g4_facts`; fraud minutes are the EP's alone (agent, system, client service, staff, senior, manager not allowed); the approval is human-only in the register and the generated module; code never sends the management inquiry; client principals are denied every A-04 write.
- Fix the suite surfaced: `fraud_minutes.approved` was not in I-AGENT-NEVER. Added to `docs/architecture/human-only-actions.yaml`, regenerated `kernel/_human_only_actions.py`, migration `0662_a04_fraud_minutes_human_only.py` on 0661 (DEC-2223).

## Partial
- UI invariants: AUD-08's existing test covers "only Margaret sees the approve controls"; AUD-05 and AUD-07 non-EP persona checks are not added here. The "one card covers every pending proposal" check is not added.

## Progress log
- 2026-11-03: written; ruff and pyright clean; not run (end pass). Red diff (protected register + migration) goes to the end security review.
