---
id: TASK-7321
title: "Main CI after S37: ruff, pinned sets, migration test isolation, journey accessibility"
spec: SPEC-000  # sprint record
acceptance_criteria: [AC-1]  # main ci green on the jobs S37 turned red
risk_zone: green
status: in-review
branch: s37-ci-fix
worktree: /Users/ayushkbhatia/Accrued/abacus-s37
created: 2026-11-12
updated: 2026-11-12
---

## Objective
CI run 43125096645 on 5953d3e72 (#1736) failed stage 1, integration shards 2, 4 and 9 and both
fixture journey shards. The run before it (46a8a067f) failed only the eval stage, so every red here
is S37's. Fix each at its root; no test is weakened.

## Fixes
- Stage 1: two E501 lines in `abacus_tools/workflows/record_s37_runs.py`'s docstring (the history
  rename in #1736 lengthened them after the last ruff run).
- Shard 2, `test_ac20_the_real_update_column_declarations_match_the_contract`: the pin now lists
  T-05-T17's tables (0821): `entity_return_profiles`, `partners`, `ownership_periods`,
  `interest_transfers`, `allocation_rungs`, and `k1_packages.partner_id`. They match the
  migration's grants and `tax/registry.py`.
- Shard 4, `test_platform_schedules`: `run_events_prune:platform` (P-10-T44) joins the pinned ids,
  with its workflow type, daily interval and batch queue asserted.
- Shard 9, 20 failures from one cause: `test_a03t06_taxonomy_db`'s up-down-up ran on the session
  database. 0671's downgrade `DELETE`s its `tax_returns` rows as the owner under forced RLS, so it
  sees none, and its CHECK then fails on a row another test left. The half-downgraded database broke
  the 19 tests after it (missing `deliverables`, `ocr_daily_caps`, `access_expires_at`, the
  human-only list). This test and `test_a03t05_sampling_tables`'s (the other shared-database
  round trip crossing 0671) now use their own database, as `test_t01t08_consents` does. 0671 is
  on main and is not edited.
- Fixture journeys (axe):
  - TAX-05 tree rows and TXI-01 worksheet items used `aria-selected` on plain `div` and `li`. They
    now use `aria-current`, and TAX-05's unit test reads it.
  - SHL-17's details `<dl>` held a `<p>`. The row text now sits between two `<dl>`s.
  - The to-do row's unread dot, and TXI-01's "Created this year" and "New this year" marks, carry
    `role="img"` with their labels.
- j06 10 used TAX-05 frame `f` (loading). It now uses frame `e` (all approved) and asserts that
  "Request final approval…" is disabled.
- j16 (P-05-T15): A2 asserted HOME-01's mention band, which is unwired until Apr 20, 2028 (P-29
  rule 2). The I-01-T25 "J16 · Home mentions band" test already holds A2 as `fixme`, so the P-05-T15
  test is now A1 alone. Flagged: P-05-T15's A2 waits on I-01's wiring.

## Progress log
- `2026-11-12` — CI reds read and fixed (TASK-7321). Mistake twice: a pinned-set test missed after a
  rename (S37 end pass, then this). The lesson stands: run the full unit, contract and integration
  shards after the last edit, not before it.
