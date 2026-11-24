---
id: TASK-8942
title: "Q-05-T27: Independent AC tests and goldens for practice and consultations"
spec: SPEC-711
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: amber
status: in-review
branch: s53-q05t27
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-23
updated: 2026-11-23
plan_key: Q-05-T27
---

## Objective
Independent AC tests and golden figures (ADR-078) for practice and consultations code. Acceptance: Tests pass on main and fail on a one-output or one-row drift in any seed figure.

## Done
- tests/unit/practice/test_q05t27_ac_goldens.py (6): five agents' outputs/overrides/rates firm-wide and Denver as typed literals; totals 3,410 / 206 / 6.0%; tolerance edge 7.96% and 8.04% not above, 8.08% above; unrated agent never above; accuracy 96.8% over 145; register 24/38/58
- tests/integration/backfill/test_q05t27_reserved_roles_ac.py (3): evaluation conclusion refused to firm admin and manager; resolve-difference refused to a manager; quality reads never reach a client

## Progress log
- `2026-11-23` — 2026-11-23: unit goldens pass (6); integration in the end pass. Projection rebuild equality and monitoring dedupe are held by the Q-05-T07/T08 service suites.
