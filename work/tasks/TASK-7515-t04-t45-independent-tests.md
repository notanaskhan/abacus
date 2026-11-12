---
id: TASK-7515
title: T-04-T45 independent AC tests for T25, T31, T37 and T38 (ADR-078)
plan_key: T-04-T45
spec: SPEC-649  # T-04 §6; AC-4.3 to AC-4.5, AC-6.x, AC-9.x
acceptance_criteria: [AC-9.3]  # the agent never approves, resolves, confirms, signs, sends or requests approval; a revoked consent stops the next tool call
risk_zone: red
status: in-review
branch: t04-t45-agent-ac
worktree: /Users/ayushkbhatia/Accrued/abacus-s39
created: 2026-11-12
updated: 2026-11-12
---

## Objective
ADR-078's independent suite for the tax agents: INV-1 on every write path, 422 `uncited_change`,
numbers by reference, budget and step limits, consent revoked mid-run going `waiting_on_inputs`,
the fix runner never resolving, DF-04's capability states.

## Plan
- `backend/tests/unit/tax/test_t04t45_independent.py`, from SPEC-649, T-04 §6 and the rows'
  acceptance: the four capabilities' specs (task scope, tool kinds, autonomy, plans, limits,
  `client_data: none`), the matrix's agent decisions on every human-only action of the tax,
  review, issue, proposal, checkpoint and sign-off families, number provenance in the fix runner,
  the analyst and the drafter, C19 asked on every TRI call (a revocation between two calls refuses
  the second), every run waiting on inputs with no model call, and the assistant's DF-04 words.
- Written in the solo session (DEC-1668 as amended): no implementation file changes.

## Progress log
- `2026-11-12` — Suite written (DEC-4515). It runs at the S39 end pass.
