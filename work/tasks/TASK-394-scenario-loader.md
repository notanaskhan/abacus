---
id: TASK-394
title: Scenario loader - replay with trace ids, settle barrier, local and staging modes (F-04-T13)
spec: SPEC-307
acceptance_criteria: [AC-1, AC-3, AC-7]
risk_zone: amber
status: done
epic: F-04
plan_key: F-04-T13
branch: f04-t13-scenario-loader
created: 2026-10-22
updated: 2026-10-22
---

## Objective
"`make seed-demo` loads E0 idempotently with scenario trace ids; refuses non-loopback DSNs and
production."

## Plan
New `abacus_tools/synthetic/scenarios/brightwater_hale/loader.py`. No migration, flag or
registry edit. The Make targets follow in F-04-T15 (Makefile protected). Rollback: revert the
commit.

## What changed
- `load(dsn, snapshot, holdouts, staging=, wait=)` replays `scenario.build(...)` in dependency order. The order is firm, offices, people, then clients; the timeline orders same-instant events by label, which would put clients first.
- Each event runs inside `kernel.clock.frozen(event.at)` under an OpenTelemetry span whose trace id is `trace_hex(event)`.
- **Decision:** `trace_hex` is the first 32 hex digits of the sha256 of `scenario:<SCENARIO_VERSION>:<event_id>`. `audit_events.trace_id` only accepts 32 hex digits (migration 0011), so the literal `scenario:` string can't be stored. Tests recompute the hash.
- **Idempotency:** an event whose trace already has an audit row is skipped, so a second run replays 0 events and writes no audit rows.
- **Clients** go through `organisations.api.create_client` under the relationship partner, as a human actor. Only each client's primary entity is created; further entities and client attributes wait for their service.
- **Firm, offices, people and memberships** have no owning service yet; tenant provisioning (Q-01) and directory sync will own them. The loader writes them as the database owner in a transaction that sets the event's tenant, actor and `app.now`, plus the audit row the service would have written. `seed_dev` bootstraps the same way.
- **Settle barrier:** waits for the tenant's outbox to drain, with a 120 s timeout (`SettleTimeout`). The workflow-idle check comes with the first slice that starts workflows. `--no-settle` is for machines with no relay.
- **At the end:** the `seed_dev` flags are turned on for the firm, and the demo clock is set to `offset` at the snapshot instant through `identity.set_demo_clock` as the firm admin.
- **Guards:**
  - production is refused in every mode;
  - a laptop load needs a loopback DSN and `db_guard.violations()` to be empty;
  - `--staging` needs `environment=staging`, refuses while a `deploy-staging` run is in progress (`gh run list`), and refuses an existing firm that isn't synthetic.
- **Tests:** `tests/unit/scenarios/test_scenario_loader.py` (guards, trace ids, order, handler coverage) and `tests/integration/test_scenario_loader.py` (E0 with a holdout: traces on audit rows, client count, synthetic firm, offset clock, second run writes nothing).

## Progress log
- 2026-10-22: ran the unit tests (10 passed) and the integration test (1 passed). ruff and pyright are clean.
