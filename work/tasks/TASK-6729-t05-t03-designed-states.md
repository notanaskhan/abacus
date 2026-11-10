---
id: TASK-6729
title: "T-05-T03: the states the handoff lacks (agent-off, flag-off, consent-blocked, import-mode, entitlement-locked) in the eight TXP screen contracts"
spec: SPEC-651
acceptance_criteria: [AC-0]
risk_zone: green
status: in-review
branch: s35-t05-t03
worktree: /Users/ayushkbhatia/Accrued/abacus-s35
created: 2026-11-10
updated: 2026-11-10
plan_key: T-05-T03
---

## Objective
Each of the eight screens has a designed agent-off, flag-off and consent-blocked state, and none renders blank.

## Plan
- `docs/screens/TXP-00`, `01`, `02`, `05`, `06`, `07`, `10` and `11.md`: each Deviations section gains a "Designed states the handoff lacks" table with five states (agent off, flag off, consent blocked, import mode, entitlement refused).
  - Each row says what renders, and that nothing renders blank (SPEC-651 F13).
  - The consent line is the spec's: "§7216 AI consent — Ridgeline (1 of 2 signed)".
  - Strings with no handoff source are marked undesigned.

## Progress log
- 2026-11-10: written; validate_docs at the end pass.
