---
id: TASK-7818
title: "Mutation weekly: identity/authz split across shards by mutant number, the outliers weighted by cost, the shards' .meta merged (Q-03-T147)"
spec: SPEC-000  # row Q-03-T147 (the weekly run measures every red scope inside its budget)
acceptance_criteria: [AC-1]  # every weekly shard inside 230 minutes; identity/authz 0 not run
risk_zone: red  # the weekly mutation workflow and its driver; no product code
status: in-review
epic: Q-03
plan_key: Q-03-T147
branch: lo38-mutation-split
worktree: /Users/ayushkbhatia/Accrued/abacus-lo38-mutsplit
created: 2026-11-13
updated: 2026-11-13
---

## Objective
Run 43330118713 (eight shards, TASK-7817) passed its floors, but shard 4 ran out of its 230
minutes holding `backend/src/abacus/modules/identity/authz/__init__.py`: 348 of its 1,708 mutants
were never run. Make every shard of the weekly run finish inside its budget, without lowering a
floor or touching the protected `backend/mutation-thresholds.yaml`, `SCOPES` or `[tool.mutmut]`.

## What the run measured (its eight `mutation-meta-*` artifacts and job logs)
- Setup (mutmut's stats pass and clean tests over the whole unit suite) took 65 to 107 minutes
  on every shard, not only on shard 4: 101, 107, 89, 97, 85, 86, 90 and 65. That leaves about
  120 minutes, or 480 CPU minutes on the runner's four workers, for mutants.
- identity/authz: 480 CPU minutes for the 1,360 mutants it ran. mutmut runs the cheapest first,
  so the 348 left are its dearest: the last 146 it ran took about 117 CPU seconds each (most of it
  pytest collecting the test files every mutant of a function `authorise` reaches). 324 of the
  348 are in `authorise` itself. The file's whole cost is 1,170 to 1,640 CPU minutes (120 to 200
  s for each mutant not run), 50 to 70 s a line.
- The rest of the red scope: about 0.4 CPU s a line, with three more outliers: evidence/pii.py
  (17 s a line, 271 CPU minutes), evidence/form_extraction.py (30, 261) and
  kernel/crypto/payload_codec.py (92, 126). They fit today by luck of the line-count draw.

A split of the file by function name (two halves, balanced by line count) cannot fit: the half
with `authorise` would hold its 324 mutants, about 160 wall minutes after setup on its own. So
the split goes by mutant number instead, and every function's mutants spread over all parts.

## Plan
- `backend/src/abacus_tools/quality/mutation.py`:
  - `WEEKLY_HEAVY`: the four outliers with their measured CPU s a line; identity/authz weighted at
    80 (the high estimate rounded up) with `parts=5`.
  - `weekly_plan`: every other file weighted by its line count as before; the outliers by
    `lines × s a line / 0.4`; a split file's parts are the last digits of the mutant number
    (`digit_parts`: 05, 16, 27, 38, 49), kept in different shards (`shards(..., apart=)`).
    A shard holding a part gets mutmut 3.8 mutant-name globs in the plan (`mutants`): the part's
    `abacus.modules.identity.authz.x_*__mutmut_*[05]` and `...xǁ*__mutmut_*[05]`, and
    `<module>.x_*__mutmut_*` / `<module>.xǁ*__mutmut_*` for each of its other files. A shard
    with no part gets none and runs every mutant of its files, as before.
  - `merge_metas` / `read_metas(*roots)`: the copies of one source's `.meta` from several shard
    folders merge per mutant; a result (killed, survived, timeout, no tests) wins over a skipped
    mutant, which wins over None. `summarise --mutants` takes one folder per shard.
- `.github/workflows/mutation-weekly.yml`: the shard passes the plan's globs to `mutmut run`;
  the floors job downloads each shard's artifact to `backend/mutation-shards/mutation-meta-N`
  (no `merge-multiple`, which kept one shard's copy of a split file) and summarises them all.
- Tests: `backend/tests/unit/quality/test_mutation_driver.py` (the split covers every function
  and every mutant of identity/authz exactly once, each part takes mutants of every function, the
  other files' globs take none of the split file's; parts go to different shards; the merge keeps
  decided results in either order; summarise merges shard folders) and
  `backend/tests/unit/tools/test_mutation_workflows.py` (the globs reach mutmut; per-shard
  download; summarise over the shard folders).
- `WEEKLY_SHARDS` stays 8. Nothing protected changes.
- Rollback: revert the commit; the workflow and driver go back to one plan per shard by lines.

## Simulation (plan against run 43330118713's measured CPU per file; setup taken at 107 minutes)
| Shard | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
|---|---|---|---|---|---|---|---|---|
| Estimated minutes (120 s a mutant not run) | 168 | 174 | 168 | 169 | 176 | 201 | 200 | 206 |
| Estimated minutes (200 s a mutant not run) | 191 | 197 | 191 | 192 | 199 | 201 | 200 | 206 |

Checked against the run's real mutant names: all 328 red files' mutants are matched by exactly
one shard; the authz parts hold 319, 368, 354, 340 and 327.

## Progress log
- 2026-11-13: run 43330118713 read (artifacts and logs in the session scratchpad). mutmut 3.8.0
  read: `mutmut run NAMES` filters every mutated file's mutants by fnmatch, so a split shard's
  globs must name its other files too; clean tests still run the whole suite.
- 2026-11-13: built. ruff, ruff format and pyright clean on the three files; 5,079 tests in
  tests/unit/quality and the workflow tests pass. Weekly run 43393671620 dispatched on the branch.
- 2026-11-13: run 43393671620: shards 1, 2, 4, 5, 6 and 7 succeeded. The merge counted 1,354
  authz mutants decided across the four parts that ran. Shard 8 ran out of time (166 minutes of
  setup on 39.9k lines: the weight counted mutants, not setup). Shard 3 failed in mutmut's stats
  pass on a load-test timing race. Both are fixed in TASK-7832 (DEC-4825).

## Rows
- Q-03-T147: still partial (the ratchet is AY's to approve, TASK-7817); this task closes the
  over-budget shard that TASK-7817 left.

## Decisions made during this task
DEC-4816.
