---
id: TASK-9004
title: "C-02-T46: W-9 requests and the filing record"
spec: SPEC-000
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: amber
status: in-review
branch: s54-c02-t46-filing-record
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-26
updated: 2026-11-26
plan_key: C-02-T46
---

## Objective
Two W-9 requests reach POR-11, the January batch exports six forms and records Filed · IRIS then Accepted, and no code path calls an IRS host.

## Done
- closes/information_return_batches.py: W-9 requests (request items created and sent by the person through requests.api), batch approval after the December close locks, deterministic IRIS CSV (sealed TINs opened for the file only, no-store), Mark filed · IRIS, acceptance or rejection with evidence, due date from C21
- delivery routes live (w9-requests, information-return-batches, iris.csv, filed, acknowledgement)
- tests: 4 (row acceptance end to end on Postgres, tin_missing and stale versions refused, no IRS host in closes/integrations/connections, deterministic formula-safe file)
- the Copperleaf 1099 fixtures moved to tests/integration/backfill/copperleaf_1099.py (shared with T45)
- DEC-6010

## Progress log
- `2026-11-26` — Built; T45 + T46 suites 8 passed. Human: verify the IRIS Taxpayer Portal CSV template before the first real filing.
