---
id: TASK-1206
title: Parallel backend tests with pytest-xdist — dependency, shared-state audit, Makefile and CI wiring (DEC-335)
spec: SPEC-045
acceptance_criteria: [AC-9, AC-12]
risk_zone: green
status: in-progress
epic: F-01
plan_key: F-01 (stage 2 run time)
branch: s8-pytest-xdist
created: 2026-10-25
updated: 2026-10-25
---

## Objective
Each pytest run is one process, so `tests/unit tests/contracts tests/security` takes about 15 minutes on an idle 10-core machine. Run the suites on pytest-xdist workers locally and inside the CI shards, without weakening, skipping or deleting a test. Approved by ayushkbhatia on 2026-10-25 (DEC-335).

## Plan
- **Dependency:** `pytest-xdist>=3.8.0` in the backend dev group (brings `execnet`); the allowlist's `python.dev` entry cites DEC-335. `uv lock`.
- **Wiring:** `PYTEST_WORKERS` (default `auto`; `0` is one process) for unit-style suites with `--dist loadgroup`, so a test that must run alone can be pinned with `@pytest.mark.xdist_group`; `PYTEST_INTEGRATION_WORKERS` (default 4) for the container suites, also `--dist loadgroup` (measured against `loadfile` and `worksteal`). `make test`, `test-integration`, `check`, `ci-unit` and `ci-integration` take them. CI: unit shards `PYTEST_WORKERS=4`, integration shards `PYTEST_INTEGRATION_WORKERS=2` (4-core runners).
- **Durations:** `abacus_tools.ci.shard --record` reads a report made with `-n 0` (docstring and Makefile say so).
- **Shared state:** audit module caches, `settings.cache_clear`, fixed temp paths and ports, generated files, repo-tree writes and order-dependent tests under `-n`; fix by isolating the test.
- **Rollback:** revert the commit; `PYTEST_WORKERS=0` restores single-process runs without a revert.

## Progress log
- 2026-10-25: dependency added (pytest-xdist 3.8.0, uploaded 2025-07-01; execnet 2.1.2, 2025-11-12). Makefile, CI and docs wired.
- 2026-10-25: first `-n 4` run refused to start: eight parametrisations had test ids made from fresh UUIDs or from zip bytes carrying their save time, so each worker collected different tests. Fixed with explicit `ids=` (`test_uow_api`, `test_screening_contract`, `test_import_parse`, `test_message_deliveries`, `test_unit_of_work`, `test_identity`) and a fixed zip entry time (`test_uploads`, `test_upload_policy`). Two collections in separate processes now match in order.
- 2026-10-25: `test_migrations_env.py` wrote its temporary revisions (one is `SELECT 1/0`) into the real `migrations/versions/`, where any concurrent migration to head (another worker's `migrated_db`) would apply them; they now go in a `tmp_path` version location (ED-045). `test_portal_home.py` AC-15 failed each evening, with and without workers: it seeded "past due" as UTC `current_date - 1`, which is today on the Central business date; it now seeds the business date minus a day (ED-045).
- 2026-10-25: integration: every worker has its own Postgres, S3 gateway and Temporal (session fixtures, ephemeral host ports); no integration or security test reaches the compose stack (`abacus-s3-1` and the rest), so buckets, keys, task queues and fixed ids can't collide between workers. Nothing needed `xdist_group`; nothing is left serial.
