---
id: TASK-2131
title: Q-03-T095 Security and reliability sweep 2027 Q2 (generator coverage)
spec: SPEC-000  # Q-03-T095 row; ADR-080
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: red
status: in-review
epic: Q-03
plan_key: Q-03-T095
branch: s16-q03-t095
created: 2026-10-29
updated: 2026-10-29
---

## Objective
The sweep: generator coverage (every table and condition kind), the invariant catalogue, DAST,
Inspector and GuardDuty triage, ADR-093 reliability follow-ups.

## Plan (red)
- New `abacus_tools/quality/generator_coverage.py` (tables in module SQL ⊆ TABLE_OWNERS; tenant
  tables ⊆ generated isolation; condition keys and matrix decisions have allow/deny tests), in
  `make check-fast`; test `tests/unit/quality/test_q03t095_generator_coverage.py` with seeded
  violations.
- Record: `docs/quality/sweeps/2026-10-29-security-reliability.md`.
- Rollback: revert; no runtime code changes.

## Progress log
- 2026-10-29: generator coverage 0 gaps on main; codegen --check current. DAST/Inspector/GuardDuty
  and SLO follow-ups need AWS and production access: human (Ayush). Invariant catalogue runs at
  the end review. Q-03-T096 has no gap to close on main; re-run on the S16 branches.
