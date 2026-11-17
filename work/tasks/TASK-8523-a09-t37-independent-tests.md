---
id: TASK-8523
title: "A-09-T37: Independent AC tests for component scope, live-human checks, citations and the agents' limits"
spec: SPEC-658
acceptance_criteria: [AC-4, AC-6]
risk_zone: red
status: in-review
branch: a09-t37-independent-tests
worktree: /Users/ayushkbhatia/Accrued/abacus-s49
created: 2026-11-17
updated: 2026-11-17
plan_key: A-09-T37
---

## Objective
Spec section: docs/plan/epics/A-09.md §6, §3 F6. Independent AC tests (ADR-078) for identity, component, host and agent work: component-scope 404s, human-only send with Undo, late sweep idempotence, TB mapper and proposer never adopt, approve or post, data-boundary fields, citations verified, attribution.

## Plan (red)
1. `backend/tests/security/test_a09t37_component_agent_independent.py` (25 tests, ac-test-author ayushkbhatia): the room guard and room read refuse another component and non-human or firm callers (404); the message rule; the proposer's and the mapper's runs refuse agents and support sessions; an unverified E3 cell blocks its proposal before any write; an E3 without a cell is never kept; both capabilities propose only and stay client_data none; the agent is denied every decision; elimination.agent_propose is held by no person; model inputs carry no amounts; agent proposals are the agent's on behalf of the initiator; the Undo and late-sweep SQL guards.
2. Also fixes A-09-T34's test typing.

## Progress log
- `2026-11-17` — Built in the S49 sequential stack. 25 passed (run once). Grant expiry, archive revocation and walls on Harlow & Pike need the seeded database and run at the end pass with the A-09-T26 harness. Gates and tests run once at the S49 end pass (build first, test last).
