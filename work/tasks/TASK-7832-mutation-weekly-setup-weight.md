---
id: TASK-7832
title: "Mutation weekly: shard weights count setup, and the load-test runner builds bodies before its clock (Q-03-T147)"
spec: SPEC-000  # row Q-03-T147 (the weekly run measures every red scope inside its budget)
acceptance_criteria: [AC-1]  # every weekly shard inside 230 minutes; identity/authz 0 not run
risk_zone: red  # the weekly mutation plan and a load-test tool; no product code
status: done
epic: Q-03
plan_key: Q-03-T147
branch: mutation-setup-weight
worktree: /Users/ayushkbhatia/Accrued/abacus-mutsetup
created: 2026-11-13
updated: 2026-11-13
---

## Objective
Follow-up to TASK-7818 (#1855, on main). Its confirming run, 43393671620, had six of eight
shards succeed: the four authz parts that ran finished in 96 to 177 minutes, and the merge counted
their 1,354 decided mutants. Two shards failed. Shard 8 ran out of time, and shard 3 failed in
mutmut's stats pass. Fix both so a weekly run has every shard succeed and identity/authz
0 not run.

## What run 43393671620 measured
Run 43393671620 (the first weight) showed setup is not a constant: it grows with the code a
shard mutates, since every mutated function's trampoline slows the stats pass and the clean
tests. Measured on its shards: 3.4k lines 49 to 80 minutes, 19.5k and 19.9k lines 104 and 117,
39.9k lines 166. So setup is about 55 minutes and 2.8 more per 1,000 lines, and the mutate step
took setup + its mutants' CPU over four workers + up to 8 minutes, on every shard that finished.
The first weight counted only the mutants (an ordinary line at 0.4 CPU s), so the outliers
weighed 2.7 times too much and shard 8 took 84 files and 39.9k lines: 166 minutes of setup,
then out of time.

The weight now counts both: `lines × (0.67 + s a line ÷ parts) ÷ (0.67 + 0.4)`, where 0.67 is
the setup per line in CPU seconds at four workers. Every ordinary file still weighs its line
count; every part of a split file pays the whole file's setup. identity/authz is weighted at 70
s a line (measured: about 1,370 CPU minutes, 58 s a line; `authorise`'s mutants 158 s each).

Estimated mutate steps for the new plan (55 + 2.8 a 1,000 lines + CPU ÷ 4; CPU per file from
43330118713, authz per mutant from 43393671620):

| Shard | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
|---|---|---|---|---|---|---|---|---|
| Lines (k) | 9.8 | 9.8 | 9.8 | 9.8 | 9.8 | 13.3 | 13.1 | 20.8 |
| Estimated minutes | 165 | 177 | 180 | 144 | 191 | 173 | 174 | 179 |

The model missed 43393671620's shards by up to 16 minutes of setup and 8 of tail, so the worst
shard should finish by about 215 of its 230 minutes. Checked against the real mutant names of
both runs: every mutant of all 328 files is matched by exactly one shard.

## Shard 3
`tests/unit/tools/test_q03t044_load_content.py::test_ac_each_user_plays_only_its_personas_groups_with_its_own_token`
failed in mutmut's stats pass with `KeyError: '/v1/me'`. The load-test runner started its 0.3 s
clock before the first user built the 300-row PBC workbook (`bodies.pbc_import_300`, cached per
process). The stats pass's tracing slowed that build until it used the whole window, so the client
users never made a request. A body is the run's fixture, not its load, so the runner now builds a
scenario's bodies before its clock starts and reuses them.

## Plan
- `backend/src/abacus_tools/quality/mutation.py`: `WEEKLY_SETUP_SECONDS_PER_LINE = 0.67`.
  `weekly_plan` weighs a heavy file's unit at `lines × (0.67 + s a line ÷ parts) ÷ (0.67 + 0.4)`,
  so each part of a split file pays the whole file's setup and an ordinary file still weighs its
  lines. identity/authz is weighted at 70 s a line (was 80).
- `backend/src/abacus_tools/loadtest/run.py`: the scenario's bodies are built once, before
  `began`.
- Test: `test_t7832_bodies_are_built_before_the_clock_so_every_user_gets_its_turn` uses a body
  slower than the run itself: every persona still makes its requests, and the body is built once.
  The split and merge tests from TASK-7818 hold unchanged.
- Rollback: revert the commit. The weights go back to mutants only, and the runner goes back to
  building each body inside the run.

## Progress log
- 2026-11-13: run 43393671620 read: artifacts merged with `read_metas`, setup per shard taken
  from the logs, and the model fitted. Built. ruff, ruff format and pyright are clean; 108 tests
  pass (the load-content, load-test, mutation driver and workflow tests). Weekly run dispatched on
  the branch (see the PR).
- 2026-11-13: run 43428320249 on the branch succeeded. All eight shards took 121 to 218
  minutes of the 250-minute job (shard 1 was slowest: 218). The floors job passed.
  identity/authz is 71.1%, with 1,466 killed and **0 not run**. Every scope has 0 not run and
  meets its floor. Renumbered from TASK-7828/DEC-4821 (taken on main by the lo39 end pass) to
  TASK-7832/DEC-4825 on rebase.

## Rows
- Q-03-T147: partial. Run 43428320249 decided every identity/authz mutant (71.1%, floor 62);
  raising its floor is AY's to approve. Shard 1's 218 minutes is a thin margin: the next red
  file to grow may need another split part.

## Decisions made during this task
DEC-4825.
