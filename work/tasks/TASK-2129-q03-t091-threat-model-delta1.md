---
id: TASK-2129
title: Q-03-T091 Threat-model refresh for pen-test delta #1
spec: SPEC-000  # Q-03-T091 row; ADR-064 governs the model
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: amber
status: in-review
epic: Q-03
plan_key: Q-03-T091
branch: s16-q03-t091
created: 2026-10-29
updated: 2026-10-29
---

## Objective
`docs/architecture/ai-threat-model.md` covers every delta #1 surface (client-facing portal flows,
the live ledger OAuth connector, the inbox, third-party rooms) before the Fri Jun 18, 2027 pin.

Acceptance (backlog row): "The model covers every delta #1 surface before the Fri Jun 18 build
pin." N reviews.

## Plan (amber)
Docs only: a delta #1 scope table, 17 threat rows (PD, PS, TP, LC, IX), two gaps, a review row.
Every cited test path checked to exist; build state read from the flags and route stubs on main.
Rollback: revert.

## Progress log
- 2026-10-29: written (self-review). N's review is the acceptance and is open. Re-read the build
  state before the Jun 18 pin: N-01-T14 and N-02-T23 to T29 decide PD-04, PS-01, PS-02.
