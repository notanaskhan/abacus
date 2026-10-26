---
id: TASK-1288
title: "Load-test harness part 1: abacus_tools.loadtest.run on httpx and asyncio with YAML scenarios"
spec: SPEC-000  # no Q-03 SPEC: the acceptance is Q-03 E1 (docs/plan/epics/Q-03.md) and the T035 row
acceptance_criteria: [AC-1]  # Q-03 E1: make loadtest PROFILE=smoke writes p50/p95/p99 per endpoint group
risk_zone: red
status: in-review
epic: Q-03
plan_key: Q-03-T035
branch: s9b-run-records-loadtest
created: 2026-10-26
updated: 2026-10-26
---

## Objective
`make loadtest` prints "not implemented" and `abacus_tools/loadtest/__init__.py` is empty.
Q-03 E1: `make loadtest PROFILE=<p>` runs YAML scenarios on `httpx` and `asyncio` and writes
p50/p95/p99 per endpoint group, with no new dependency (no k6, no Locust). Acceptance:
"make loadtest PROFILE=smoke runs against a local stack and writes p50/p95/p99 per endpoint
group."

## Plan
- **Package** `backend/src/abacus_tools/loadtest/`:
  - `scenario.py`: the YAML scenario model (Pydantic, `extra="forbid"`): duration, virtual users,
    think time, seed, persona, endpoint groups (weighted request sequences with expected statuses
    and an optional p95 target), SSE streams (count, hold, first-event target) and Temporal-client
    operations (`count_workflows`, `start_workflow`, at a rate); the pass rule's error-rate ceiling.
  - `stats.py`: client-side nearest-rank percentiles (p50, p95, p99, max), counts, errors, rate;
    a group passes when its p95 target holds; the run passes when every group does and the error
    rate stays below the ceiling (Q-03 E2's shape; chapter 10's targets come with T043's scenarios).
  - `run.py` (`python -m abacus_tools.loadtest.run --profile smoke`): the runner (one
    `httpx.AsyncClient`, asyncio virtual users, `httpx` SSE streams, the Temporal client), the
    report (JSON plus a Markdown table) under `backend/.local/loadtest/` (git-ignored: results only,
    never committed), and the exit code (1 when the pass rule fails).
  - `scenarios/smoke.yaml`: a few seconds, two users, read endpoints only, one Temporal read.
- **Local only**: refuses a non-loopback API or Temporal target and any environment but `local`
  and `test`; tokens are minted with the local sign-in server's key (`fakes.oidc_server`), which
  only a local API trusts. No AWS, no Terraform, no hosted database.
- **Makefile**: `loadtest` runs the module with `PROFILE` (default `smoke`) against this
  checkout's API port and stack.
- **Dependencies**: httpx, pyyaml, pydantic and temporalio, all already allowed; nothing new.
- **Tests first**: `tests/unit/tools/test_loadtest.py` (scenario loading and validation,
  percentiles, the pass rule, SSE parsing and the runner end to end on `httpx.MockTransport` with a
  fake Temporal operation, the loopback refusal, the report files).
- **Rollback**: revert the commits; `make loadtest` prints "not implemented" again.

## Progress log
- 2026-10-26: planned.
- 2026-10-26: built. Tests first (`tests/unit/tools/test_loadtest.py`, 21), then `scenario.py`,
  `stats.py`, `run.py`, `scenarios/smoke.yaml` and the Makefile target. DEC-397.
- 2026-10-26: smoke run, verified end to end without touching the shared dev database: a
  throwaway migrated Postgres (`schema_check.provisioned_database`), `seed_dev`, this checkout's
  API on :8091 and the dev Temporal for the visibility read; the same command `make loadtest`
  runs. 5.06 s, 2 users, 203 requests, passed (0 errors); p50/p95/p99 ms: health 2.9/5.4/9.1, me
  23.3/86.0/239.3, record_lists 13.5/22.2/33.8 (target p95 300), temporal_visibility
  3.6/10.5/10.5. The first runs failed honestly: `/v1/clients` and `/v1/engagements/index` are
  behind flags (404) locally, so the profile reads `/v1/notifications` instead.
- Not verified: `make loadtest` itself against `make dev` (no dev API was running; the shared dev
  database is at 0102), SSE against a real route (none exists yet), `start_workflow` load.

## Definition of done
- [x] Unit tests (21) pass; the smoke profile writes p50/p95/p99 per endpoint group locally.
- [x] Backend gates.
- 2026-10-26: security review L4: `start_workflow` runs only in the local `default` namespace
  (DEC-397 note); 22 unit tests.
