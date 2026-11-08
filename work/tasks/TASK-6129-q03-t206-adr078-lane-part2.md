---
id: TASK-6129
title: "Q-03-T206 ADR-078 catch-up lane part 2: R-02-T04, A-07-T15, A-05-T48 suites and lane record"
spec: SPEC-000  # row (Q-03-T206)
acceptance_criteria: [AC-1]
risk_zone: red
status: done
epic: Q-03
plan_key: Q-03-T206
branch: s30-q03-t206
worktree: /Users/ayushkbhatia/Accrued/abacus-s30
created: 2026-11-08
updated: 2026-11-08
---

## Objective
ADR-078 catch-up lane 2027 Q4 part 2: independent AC suites for red and amber work deferred under a cut list, written from the spec and contract only.

## Plan
- Independent suites from the rows: `tests/unit/portal/test_r02t04_bundle_independent.py` (client actions deny agent and system, decisions never the agent's, I-AGENT-NEVER names R-02's client decisions, portal to reporting edge, CLIENT-DECISION-001 catches a planted decide), `tests/unit/assurance/test_a07t15_gates_independent.py` (G6-G9 registered, external unchanged, in_app live blockers, compilation and preparation skip G6 and G7, failing provider unmet), `tests/integration/test_a05t48_estimates_rp_independent.py` (five tables with forced RLS, parties in interest hold no money column, prohibited transactions a security_invoker view over ebp_late_remittances).
- `docs/plan/status/S30-adr078-lane.md`: part 1 rows closed in S30 (12), still open, and S30's own red and amber rows.

## Progress log
- 2026-11-08: built. The two unit suites pass locally (70). The integration suite is written, not run (end pass).

## Decisions made during this task
None.
