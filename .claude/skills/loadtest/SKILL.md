---
name: loadtest
description: Run, read and record a load test with abacus_tools.loadtest - rehearse a profile on your own stack, seed x1/x25/x100 synthetic firms on the perf stack, read p50/p95/p99 and OTel, write results only, destroy the stack. Never against a database a hosted build is using. Use for Q-03 load windows (T052, T100, T131, T176 and later), for a new load profile, or for the post-deploy x1 smoke.
---

# Load test

**Runbook of record:** `docs/ops/loadtests/README.md`. Targets and scenarios: chapter 10 section 10.11 (`docs/plan/10-quality-strategy.md`). Harness: `backend/src/abacus_tools/loadtest/` (`run.py`, `scenario.py`, `bodies.py`, `scenarios/*.yaml`). Firm profiles: `backend/src/abacus_tools/synthetic/fleet.py`.

## Never
- Load a database a hosted build, migration or seed is using: staging's shared database, production, or anything while a deploy lock is held. The perf stack (QD-6) or your own laptop stack only.
- Loosen the harness's loopback and environment refusal (DEC-397) or the fleet loader's guard to make a run go. A new target is a reviewed change (Q-03-T036, T043), not a flag.
- Commit a result with a hostname, account ID, token, tenant id, request body, client data or a money amount. Results only, in `docs/ops/loadtests/<yyyy-mm>.md`.
- Lower a p95 target or the 0.1% error ceiling to pass. A failure is a reliability-only batch and a re-test (ADR-093).
- Leave the perf stack up past its window.
- Seed x25 or x100 anywhere but the perf stack's database: the fleet loader refuses a host that does not start `abacus-perf`; never rename a database to get past it.

## Add or change a profile
1. One YAML file per profile in `scenarios/`, validated by `scenario.Scenario` (strict: unknown keys fail). Name groups after the journey step they shape (`j04_pbc_requests`).
2. Who calls: one `persona`, or `personas` with weights and the groups each plays (a client persona never plays a staff group). Subjects are local sign-in subjects: `scenario-<slug>` for Brightwater Hale people, `fleet-NNN-staff-NN` for fleet firms.
3. Targets: put chapter 10 section 10.11.1's p95 on each group it covers (record read 300 ms, list with counts 500 ms, mutation 400 ms). No target on a step that is padded by design (the portal sign-in start's 0.5 s floor).
4. Ids come from `--var` (`{engagement_id}` in a path); add derived ones to `journey_vars.py` so `make loadtest` passes them. A generated body is a named builder in `bodies.py` (`body: pbc_import_300`); a JSON body is static.
5. Tests: the profile loads in `tests/unit/tools/test_loadtest.py` (every committed profile) and its own assertions in a `test_q03tNNN_*.py` file, run against `httpx.MockTransport`. Never a network call in a test.

## Run
- Always first: `make loadtest PROFILE=<name> DRY_RUN=1` (the plan, ids filled, nothing sent).
- Chapter 10's scenarios and the x1 smoke's trend: runbook section 4 (what a human does during each; `abacus_tools.loadtest.trend` for the +20% ticket and the quality-report row).
- Laptop rehearsal: `make dev`, `make migrate`, `make seed-demo SLICE=portal`, then `make loadtest PROFILE=smoke`, then `PROFILE=journeys`. Runbook section 1.
- Perf stack: runbook sections 2 to 6, in order, each step's precondition checked.

## Read and record
- Pass rule: every target held, error rate under 0.1%, no SLO alarm. Compare client p95 with server p95 from OTel for the same window before blaming the app.
- Write the result file (runbook section 5) in the same PR as any fix it causes, or alone. Say "holding for the batch" on the PR.
