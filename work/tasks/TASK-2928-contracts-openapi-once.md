---
id: TASK-2928
title: Build the OpenAPI document once per process; stage 1 timeout 15 minutes
spec: SPEC-000  # ADR-013 export; CI stage 2 "schema and api-client" (15-minute limit)
acceptance_criteria: [AC-1]  # the schema and api-client job completes on CI
risk_zone: green
status: in-review
epic: F-01
plan_key: F-01-T06
branch: ci-contracts-openapi-cache
worktree: scratchpad worktree of the S24 end-pass repair session
created: 2026-11-02
updated: 2026-11-02
---

## Objective
CI's `stage 2 schema and api-client` job was cancelled at its 15-minute limit on every recent
run (#1074, #1095, main), so the API client's drift check never ran on CI.

## Scope
61 of 88 contract modules call `abacus.api.export_openapi.document()` at import, and each call
built the app and its schema again (about 8 s). `document()` is now cached per process. Running
the suite under xdist did not help (each worker repeats the collection): 14m22s against 13.5
minutes serial. Rollback: revert.

## Progress log
- 2026-11-02: cached. Local `pytest tests/contracts`: 13.5 min → 6m47s (6601 passed); the whole
  `make ci-contracts` 10m26s, inside the job's 15 minutes.
- 2026-11-02: on CI the schema and api-client job passed in 4m49s (contracts 2m48s). Stage 1
  still hit its 10-minute limit (it needs about 12: ruff+pyright+lint-imports 3m54s, banned
  patterns 1m55s, web lint 1m55s). Ayush approved raising it to 15 minutes.
