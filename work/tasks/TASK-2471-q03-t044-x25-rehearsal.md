---
id: TASK-2471
title: Finish Q-03-T044 on the repo side with a laptop x25 rehearsal
spec: SPEC-000  # no Q-03 SPEC: chapter 10 section 10.11 and the Q-03-T044 row
acceptance_criteria: [AC-1]  # make seed-staging PROFILE=x25 builds 25 Brightwater-size synthetic firms through service APIs on the perf stack
risk_zone: green
status: in-review
epic: Q-03
plan_key: Q-03-T044
branch: s19-q03-t044
created: 2026-11-01
updated: 2026-11-01
---

## Objective
Sprint 21 asked for Q-03-T044 to be finished; it gates Q-03-T132. Its content is on main (#468,
TASK-1357). Prove x25 builds at the full shape, and record what stays open.

## Plan
Run `fleet.load(dsn, "x25")` on a throwaway local Postgres (testcontainers), count, re-run. Record
the result (results only) in the load-test runbook, TASK-1357, status-verified and DEC-1531. No
code change: the profile already builds.

## Progress log
- `2026-11-01` — 25 firms, 2,500 memberships, 4,600 clients, 675 audits and PBC lists, 10,800
  requests, 4,600 `client.created` audits; 9,025 writes in 76 s; re-run 0 writes in 8 s. The
  perf-stack run waits for Q-03-T036 (not built).

## Handoff
- **Current state:** PR open, held for the batch.
- **Exact next step:** when Q-03-T036 lands, `make seed-staging PROFILE=x25` on the perf stack.
