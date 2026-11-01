---
id: TASK-2821
title: A-03-T18 independent AC tests for the sampling services
spec: SPEC-580
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
epic: A-03
plan_key: A-03-T18
branch: s23-a03-t18
worktree: /Users/ayushkbhatia/Accrued/abacus-s23
created: 2026-11-01
updated: 2026-11-01
---

## Objective
- **[AC-1]** "The suite passes on main and fails when the population_not_tied guard, the
  server-seed rule or the per-item third-party grant is removed."

## Plan (amber, tests only)
- **Unit** `tests/unit/sampling/test_a03t18_seed_policy.py`: the seed rule.
  - 24 server bits.
  - A real firm never takes a seed.
  - A seed outside the range is refused.
  - Only the scenario loader seeds a synthetic firm.
- **Integration** `tests/integration/backfill/test_a03t18_sampling_independent.py`:
  - The tie guard needs every tie to agree.
  - A tied population approves.
  - An HTTP draw records a server seed, and two draws differ.
  - The third party holds one active `request_item` grant per delegated request and nothing wider; the client contact holds none of them.
  - Census fields stay out of the logs.
- **Reuse.** The integration tests reuse A-03-T10's stand-ins and A-03-T13's approved version.
- **Already covered elsewhere.** Export determinism, fan-out counts and walls are already in T10/T13's suites, so they are not repeated here.
- **Rollback:** revert.

## Progress log
- `2026-11-01`: written; ruff and pyright clean. The tests run in the end pass (build-first rule).

## Decisions made during this task
None.
