---
id: TASK-6528
title: "A-07-T35: independent AC tests for A-07-T23, T24, T26 and T27 (ADR-078)"
spec: SPEC-644  # A-07 F4-F7 (docs/plan/epics/A-07.md)
acceptance_criteria: [INV-1, INV-3, INV-4, INV-5, AC-letters]
risk_zone: red
status: in-review
branch: s33-a07-t35
worktree: /Users/ayushkbhatia/Accrued/abacus-s33
created: 2026-11-09
updated: 2026-11-09
plan_key: A-07-T35
---

## Objective
The suite fails if any letter reaches a client principal before a named EP approval or if a
regenerate drops a human edit.

## Plan (red, tests only)
`tests/unit/assurance/test_a07t35_letters_independent.py`, from the row, A-07 F4-F7 and the
invariants, against the services' public surface and the permission matrix: going concern and
opinion cards reserved to the EP, going concern locked in the report, no agent or system sets the
opinion, only the EP approves the report and letters (fresh MFA); no client principal, agent or
system sends a letter, and a rep letter without an approval of its current version never sends;
the G7 date rule in the firm's zone; no amount in a rep-letter paragraph, the general
representations locked, no materiality or amount in a planning letter; only a `tcwg` grant on the
room opens it (404 otherwise; never a firm person, agent or system); client principals and walls
answer 404; a composed draft is the initiator's, its run names the initiator and no reserved verb,
and an agent context never writes a letter itself; regenerate keeps every human edit of every kind
and refreshes the rest. No production code changes.
Rollback: revert.

## Progress log
- `2026-11-09` — Written; not run (end pass). Solo edition: independence is this separate task
  and session (DEC-3128, as DEC-3127 for P-11).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-3128 | Solo independence for A-07's letter AC tests | no (ADR-078) |
