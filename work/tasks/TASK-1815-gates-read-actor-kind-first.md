---
id: TASK-1815
title: Human-only gates read the actor kind before ctx.client (P-07-T59 security review follow-up)
spec: SPEC-332
acceptance_criteria: [AC-1]
risk_zone: red
status: in-review
epic: P-07
plan_key: P-07-T59
branch: s13r-gate-order
created: 2026-10-29
updated: 2026-10-29
---

## Objective
The low finding from P-07-T59's security review: twenty human-only checks tested `ctx.client` (and `ctx.is_support`) before `ctx.tenant.actor_kind`, so an `AgentContext` (which has neither) raised `AttributeError` (a 500, nothing written) instead of `Forbidden`. Not reachable over HTTP (`current_context` yields only `AuthContext`); reachable from a service an agent tool might call.

## Plan (red)
- Reorder each condition to `ctx.tenant.actor_kind != "human" or ctx.client [or ctx.is_support]`: pure boolean reads, so an `AuthContext` decides exactly as before; an agent or system context is refused first. 18 files (assurance, engagements, evidence, identity, methodology, organisations, portal, review).
- Test first: `tests/unit/quality/test_actor_kind_first.py` (no condition in `src/abacus` tests `.client` before the actor kind; four gates refuse an agent context with `Forbidden`). Red before (20 sites, 4 `AttributeError`), green after.
- Not changed: `audit_trail/record_activity_routes.py` reads `ctx.client` alone to 404 a client principal before authorising; it is not a human-only gate and an agent never reaches it over HTTP.
- Rollback: revert.

## Progress log
- 2026-10-29: built; the new test red then green (5 passed); contracts and the touched modules' unit suites run.
- 2026-10-29: the touched suites found a test leak on main, unrelated to the reorder: once a suite imports signatures (N-02-T09 replaces the interim G3 in the process-wide gate registry), `tests/unit/engagements/test_gates.py` reads `envelopes` and fails (3 cases; reproduced by `tests/contracts/c7_n02` then the file). The suite now pins C1's own three providers for each test. Contracts and the touched modules' unit suites: 26,971 passed before the fix, the three now pass in the leaking order.
