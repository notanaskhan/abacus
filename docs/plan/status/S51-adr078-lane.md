# ADR-078 catch-up lane 2028 Q3, part 2 (Q-03-T352)

Recorded 2026-11-20 at the S51 build. One builder, so "the other founder's session" reads as a suite
written from the row, spec and contract only, apart from the implementing work (AMENDMENT-solo).
Scope: the red and amber build rows of A-08, A-09, W-01 and C-01 (S44–S51).

## Suites of the epics, run once (2026-11-20, local, migrated Postgres)
356 passed, 1 xfailed across the 19 ADR-078 and contract rows:
C-01-T06, T08, T45, T46, T47, T48, T49 · A-08-T11, T33, T34, T35 · A-09-T06, T24, T25, T26, T35, T37 · W-01-T06, T18.

## Row → suite
| Rows | Zone | Suite |
|---|---|---|
| C-01-T14, T15, T19, T20 | amber | C-01-T46 `tests/integration/test_c01t46_close_ac_suite.py` |
| C-01-T21–T27, T58 | amber | C-01-T47 `tests/unit/closes/test_c01t47_independent.py`; C-01-T45 goldens for T22 |
| C-01-T07, T10, T16, T17, T18 | red | C-01-T48 (`test_c01t48_snapshots_ac.py`, `test_c01t48_red_rules_ac_suite.py`); C-01-T08 C9 v2.1 consumers |
| C-01-T28, T29, T30 | red/amber | C-01-T49 `tests/unit/closes/test_c01t49_agent_never.py` |
| C-01-T04, T05 (stubs) | amber | C-01-T06 consumer contracts `tests/contracts/closes/` |
| **C-01-T09, T11** (migrations) | amber | **Q-03-T352** `tests/integration/test_q03t352_catchup_independent.py` (was open) |
| A-08-T09 | red | A-08-T33 |
| A-08-T15, T19 | red | A-08-T34 `tests/security/test_confirmation_isolation.py` |
| A-08-T12, T13, T14, T16, T17, T18, T21, T22, T24 | amber | A-08-T35; A-08-T11 goldens for T10, T13, T20 |
| A-08-T23 | red | its own independent suites (three files) |
| A-09-T05, T10, T11, T13, T18, T19, T20 | red | A-09-T26; A-09-T25 goldens for T19 |
| A-09-T21, T27, T28, T29, T34 | red/amber | A-09-T37 |
| A-09-T23, T30, T33 | amber | A-09-T35 |
| **A-09-T12** (migration) | amber | **Q-03-T352** (was open) |
| A-09-T03 (stubs) | red | A-09-T06 consumer contracts |
| W-01-T07, T08, T09, T13, T15 | red | W-01-T06, W-01-T18 |
| W-01-T14 | red | W-01-T18 (admission precondition, dependents count) |
| **W-01-T04** (migration) | red | **Q-03-T352** (was open) |
| Protected bundles and registries (C-01-T02, T03; A-08-T03; A-09-T02, T04, T09; W-01-T02) | red/amber | the generated matrix, flag and registry checks in `make check-fast` (not ADR-078 rows) |
| Content slices (A-08-T08, A-09-T39, C-01-T44) | amber | their foot and scenario tests |
| Eval suites and real runs (A-08-T25, A-09-T24, A-09-T41, C-01-T31, C-01-T32) | red | the suites are protected tests themselves; the real Bedrock runs are open (no signed evaluation-account run) |

## What Q-03-T352 adds
`tests/integration/test_q03t352_catchup_independent.py` (41 tests), from each row's acceptance and its migration's stated contract, read from Postgres's catalogue:
forced RLS on every new table of `closes_v1`, `closes_v2`/`requests_cas`, C20 v2 Connect and `assurance_group`; insert-only tables refuse UPDATE and DELETE for `abacus_app`; the human-only actor_kind CHECKs on plan publishing, item resolutions and flux acceptance; no close-engine table is deletable by the app; the published-plan freeze trigger; the Analytical-only PM CHECK; the person-only deliverable review CHECK.

## Still open
- Behavioural (row-level) checks of the plan-version freeze and the two A-09-T12 refusals: the suite checks that the trigger and CHECKs exist, not a refused write on a seeded row.
- W-01-T04 "no existing column changes type" and every migration's up/down/up on a staging copy: staging work.
- A seeded-vulnerable-build run: the catalogue checks flip on a granted privilege, an unforced policy or a dropped CHECK by construction; not run as a separate mutated database.
- One assertion dropped before commit: "the app cannot DELETE `integration_oauth_states`" is not in W-01-T04's contract (states are spent by UPDATE; nothing says they are never swept), and the app holds DELETE.
