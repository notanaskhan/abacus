---
id: TASK-7720
title: I-02-T11 attention providers and work-item hooks
plan_key: I-02-T11
spec: SPEC-654
acceptance_criteria: [AC-2.2, AC-2.3]
risk_zone: amber
status: in-review
branch: i02-t11-attention
worktree: /Users/ayushkbhatia/Accrued/abacus-s41
created: 2026-11-13
updated: 2026-11-13
---

## Objective
`engagements.register_attention_provider`, a fail-closed slot, with the first providers (unmet
G1 to G3 gates that block requests; outstanding PBC against the report target) and the optional
work-item hooks `next_milestone` and `dependents`, with tax's 1065 implementation (Ridgeline K-1
release; the Feld and Shah 1040s under DEC-88's both-sides rule).

## Plan (amber)
- `engagements/attention.py` (new): slot, hooks, `dependents_visible`, `gates_blocking_requests`.
- `requests/attention.py` (new): `outstanding_pbc`; registered in `requests/api.py`.
- `tax/attention_hooks.py` (new): K-1 release milestone, K-1 recipient dependents; registered in
  `tax/api.py`.
- `agents/api.py`: export the briefing names I-02-T07's tax source imports (missing until now).
- Tests: `backend/tests/unit/engagements/test_i02t11_attention.py`.
- Rollback: revert; nothing reads the slot until Today's drill-in wires it.

## Partial
- Today's drill-in does not yet read the attention rows or the dependents (I-02-T10 left its
  assign prefill and downstream rows waiting on this row); wired in the end pass if time allows,
  else carried to I-02-T13.
- The tax hooks and the PBC provider run SQL; only the slot is unit-tested here. The DB-backed
  check runs at the end-pass scenario load (Ridgeline, Fairhaven, Northwind).

## Progress log
- 2026-11-13: built; ruff and pyright clean; tests written, not run. Found and fixed missing
  `agents.api` briefing exports from I-02-T07 (the tax briefing source would fail at call time).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-4723 | the slot, the first providers and the tax hooks | no |
