---
id: TASK-2003
title: Q-03-T082 Independent AC tests for the expand-only guard
spec: SPEC-403
acceptance_criteria: [F4]
risk_zone: red
status: in-review
epic: Q-03
plan_key: Q-03-T082
branch: s15n-q03-t082
created: 2026-10-29
updated: 2026-10-29
---

## Objective
ADR-078 independent tests for Q-03-T081, written from the row and Q-03 F4: each refused pattern,
the `contract-step` exception, the Jun 1, 2027 date switch, and window mode refusing a labelled
contract step inside a window (the guard's CLI and the release window gate).

## Acceptance
`backend/tests/unit/quality/test_q03t082_expand_only_independent.py`: 29 passed once (4 s).

## Progress log
- 2026-10-29: written from the spec; stacked on s15n-q03-t081.
