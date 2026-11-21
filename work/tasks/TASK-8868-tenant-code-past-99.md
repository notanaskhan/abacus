---
id: TASK-8868
title: Tenant codes past 99 (the integration shard hang) and faster, provable CI shards
spec: none (CI fix; DEC-5865)
acceptance_criteria: [the 100th firm with the same initials gets tnt_<initials>100, by the trigger and by provision_firm; no integration test can hang on firm creation; every test file runs in exactly one shard, proven per run]
risk_zone: amber
status: in-review
branch: ci-speed
worktree: /Users/ayushkbhatia/Accrued/abacus-ci-speed
created: 2026-11-21
updated: 2026-11-21
---

## Objective
Find why integration shards run to the 100-minute timeout, fix the cause, and make the shard
split balanced and provably complete.

## Findings
- CI audit, last 150 `ci` runs: integration shards p50 59 min, p95 99.5 min (the timeout);
  221 of 755 shard jobs cancelled. Queue waits (p95 ~97 min) are those shards holding runners.
- **The hang.** `firms_tenant_code_default()` (0921) and `provision_firm` (0987) number codes with
  `lpad(n::text, 2, '0')`, which truncates: `lpad('100', 2, '0')` = `'10'`. With `tnt_fx01`–`99`
  taken the trigger loops forever inside the INSERT (seen live: `INSERT INTO firms` active, no
  wait event, 100% CPU). `Seeder.firm` names every firm `Firm x<hex>` (initials `fx`), so the
  100th seeded firm in one test database hangs its shard. In production the 100th firm with the
  same initials could never be provisioned (timeout or unique violation at 9999).
- Shard timings: `tests/durations.json` held 89 of 748 integration files; the rest were weighted
  as the median, so shards ranged 35 to 65 minutes on the same run.
- 126 integration files each started their own Postgres container and migrated to head; every
  worker session also migrated head, base, head.

## Plan (amber)
- Migration 1003: both functions pad to two digits and keep longer numbers whole. Downgrade
  restores the 0921 and 0987 bodies verbatim. Test `test_1003_tenant_code_past_99.py` under a
  10 s statement timeout (fails, not hangs, on a regression; red without 1003, green with it).
- `provisioned_database(roundtrip=False)`: a copy of a per-process template (shared container)
  instead of a container per call, with a fail-closed check that cluster-level state is unchanged;
  `isolated=True` for callers that change roles (`test_schema_check_db`, `test_drill_verify`) and
  the session fixtures. The head-base-head round trip runs once per run in the schema_check gate.
- Shard records (`abacus_tools.ci.record`) per shard; `ci-coverage` verifies every test file ran
  in exactly one shard; main saves merged timings to the actions cache, `changes` hands one copy to
  all shards of a run.
- Rollback: revert the PR; downgrade 1003.

## Progress log
- 2026-11-21: audit done; hang reproduced on `test_g02t12_security_center_ac_suite.py` alone and
  traced to the lpad truncation; 1003 written and proven red-then-green; shard recording, proof and
  template database built; tools unit tests pass (1648).
- 2026-11-21: validation. All 124 test files that call `provisioned_database` on the template
  path, `-n 4` locally: 1545 passed, 8 xfailed, 4 failed, no cluster-state guard trips, no hangs
  (33.5 min). Three failures are pre-existing (same result with `ABACUS_TEST_DB_ISOLATED=1`, the
  old container-per-call path): `test_a03t16` fixture drift (`make fixtures` owed),
  `test_p08t22::test_t14` (g04_fixtures.py constants), `test_s38` (asserts the T05 check after
  later migrations moved it). The fourth, `test_scenario_sampling`, passes alone on both paths and
  failed under workers with "Event loop is closed" in `identity.repository.display_names`: the
  global identity engine keeps a pooled connection from an earlier test's loop (order-dependent,
  not this change); left open. Same four files single-process: 224 s old path, 171 s template path.
  Lint, pyright, import contracts clean; alembic single head 1003.
