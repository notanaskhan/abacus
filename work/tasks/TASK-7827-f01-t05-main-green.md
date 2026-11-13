---
id: TASK-7827
title: "F-01-T05: main's CI reds after S39, S40 and the lo38 batch"
spec: SPEC-000  # row F-01-T05
acceptance_criteria: [AC-1]  # main green
risk_zone: amber  # tests, the CI workflow, the path filter
status: in-review
branch: lo39-f01-t05
worktree: /Users/ayushkbhatia/Accrued/abacus-lo39
created: 2026-11-13
updated: 2026-11-13
plan_key: F-01-T05
---

## Objective
Main CI on 158d5cd14 (run 43411471339) was red in schema and api-client, 8 integration shards and
the fast evals. Each red has a cause in a change that landed without its test or wiring.

## Fixes

At merge, main already held #1899 (TASK-7637, the S40 CI repair), which fixed the same six tests
and regenerated the fixtures; those parts of this PR were dropped in favour of main's, so it lands
the evals gating and the tax agent paths only.

- `tests/contracts/t05_consumers/test_t05t24_handshake.py`: T-05-T32 landed (TASK-7408), so the
  strict xfail XPASSed; the marker is lifted and the test holds the handlers.
- `tests/integration/test_tenant_provisioning.py`: P-02-T06's two search workflows in platform's
  WORKFLOWS.
- `tests/integration/test_platform_schedules.py`: `search_drift:platform` (P-02-T06).
- `tests/integration/backfill/test_q01t43_platform_controls_independent.py`: `POST /v1/search` is a
  read sent as POST, already exempt in `identity/routing.py`.
- `tests/security/test_tri_and_offshore.py`: `run_artifact.download` is `not_offshore` (W-02-T03).
- `tests/integration/test_schema_check_db.py`: `workbench_sessions` (0850) and `daily_briefings`
  (0851) UPDATE columns, as their registries declare.
- `.github/workflows/ci.yml`: `make evals-tax-fast` ran ungated with no checkout on a diff without
  agent paths ("No rule to make target"); gated like the other eval steps, and the tax module's
  paths count as agent paths (`abacus_tools.ci.paths`).
- Fixtures: `2026-09-14T09:41` regenerated (`make fixtures`).

## Open
- `make fixtures SNAPSHOT=E0` and `SNAPSHOT=2026-09-24T10:20` need a Linux host: their seed renders
  PDFs in the isolated renderer and this Mac has no WeasyPrint libraries (`IsolationFailed`).
  Regenerated in the lo39 end pass.
- Coverage at 95% (the row's dated exception) is not shown.

## Progress log
- 2026-11-13: fixed what main's run named; targeted runs in the end pass.

## Decisions made during this task
None.
