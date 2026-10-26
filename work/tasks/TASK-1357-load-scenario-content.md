---
id: TASK-1357
title: Load scenario content from the journeys, the 300-item PBC import and the x1/x25/x100 firm profiles (Q-03-T044)
spec: docs/plan/10-quality-strategy.md section 10.11
acceptance_criteria: ["make seed-staging PROFILE=x25 builds 25 Brightwater-size synthetic firms through service APIs on the perf stack"]
risk_zone: amber
status: in-review
epic: Q-03
plan_key: Q-03-T044
branch: s10c-ops
created: 2026-10-27
updated: 2026-10-27
---

## Objective
Give the S9 harness (Q-03-T035) journey-shaped content and give `make seed-staging` the x1, x25
and x100 profiles chapter 10 section 10.11.2 sizes.

## Plan
- **Harness (additive):** `scenario.Persona` (subject, weight, groups) and `Scenario.personas`
  (one `persona` or weighted ones, never both; every group played by someone); a virtual user is
  one persona for the run and plays only its groups with its own token (`run(tokens=...)`).
  `Step.body` names a generated body (`loadtest/bodies.py`), sent with its content type.
- **Content:** `scenarios/journeys.yaml` (J02-audit-core Home and client record, J04's PBC slice
  on Northwind's 401(k) audit A1, J12-core branding, code sign-in start and shell; the A1 team
  and Dana Kowalski weighted 1:2:3:4:6) and `scenarios/pbc_import_burst.yaml` (Hannah Leclerc
  imports 300 requests through SPEC-018's request-list import while the team reads).
  `bodies.pbc_import_300`: the F-04 generator's request list cycled to 300 distinct rows.
  `loadtest/journey_vars.py` derives the ids from the scenario; `make loadtest` passes them.
- **Profiles:** `abacus_tools/synthetic/fleet.py`: x1/x25/x100 = 1/25/100 firms of the
  Brightwater shape counted from the F-04 scenario (46 seats, 184 clients, 27 audits, a 16-request
  PBC list each, two client people per audit). Clients through `organisations.api.create_client`;
  the rest bootstrapped as the Brightwater loader does (DEC-144), traced and idempotent; the
  rollout and portal flags on per firm; the loader's guard (no production, loopback on a laptop,
  staging environment and no deploy in flight with `--staging`) and a non-synthetic refusal.
  `make seed-staging PROFILE=x1|x25|x100` runs it; any other PROFILE keeps Brightwater Hale.
- **Tests:** `tests/unit/tools/test_q03t044_load_content.py`,
  `tests/integration/test_q03t044_fleet_load.py`.
- **Rollback:** revert; the harness changes are additive and `smoke` is untouched.
- Decisions: DEC-455.

## Not done (needs the builder or later tasks)
- The x25 build on the perf stack itself: `infra/envs/perf` (Q-03-T036) does not exist yet, so
  the acceptance run is the runbook's (docs/ops/loadtests/README.md, TASK-1358).
- The harness still refuses non-loopback targets (DEC-397); playing the journey mix against the
  perf stack's fleet firms needs Q-03-T036's in-VPC runner and Q-03-T043's perf target and
  per-firm ids. Authenticated portal v2 reads (POR-02 home) need a portal session minted for load,
  left to Q-03-T100's portal-heavy content.

## Progress log
- 2026-10-27: built; unit and integration tests written (results in the S10 wave C report).
