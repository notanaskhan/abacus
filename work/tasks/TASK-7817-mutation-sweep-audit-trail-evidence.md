---
id: TASK-7817
title: "Mutation sweep: audit_trail and evidence back over their floors, and the weekly run in eight shards (Q-03-T072, Q-03-T147)"
spec: SPEC-000  # rows Q-03-T072, Q-03-T147 (Q-03-T179, Q-03-T180, Q-03-T227 measured, not closed)
acceptance_criteria: [AC-1]  # no red module below its floor at the sweep
risk_zone: red  # tests for red modules; the weekly workflow; no product code
status: in-review
epic: Q-03
plan_key: Q-03-T147
branch: lo38-mutation-sweeps
worktree: /Users/ayushkbhatia/Accrued/abacus-lo38-mut
created: 2026-11-13
updated: 2026-11-13
---

## Objective
The first weekly mutation run to finish its shards (43284162288, on this branch) put two red
modules under their floors. Close them with tests, never by lowering a floor (AGENTS.md 13;
`backend/mutation-thresholds.yaml` only rises), and fix the two harness faults that run showed.

## What the run measured
| Scope | Score | Floor | Killed | Survived | No tests | Not run |
|---|---|---|---|---|---|---|
| audit_trail | 13.3% | 14% | 527 | 308 | 3,138 | 0 |
| evidence | 21.0% | 22% | 7,983 | 4,293 | 25,748 | 469 |

Every other scope met its floor (ai_gateway 27.8% of 20%, identity/authz 68.4% of 62%,
kernel/crypto 71.5% of 53%, kernel/db 22.6% of 13%, kernel/uow 6.7% of 2%; the 0% scopes:
agents/runtime 19.3%, assurance/release_archive 14.6%, compute 73.6%, kernel/realtime 62.7%,
review 4.7%, signatures 8.3%).

Harness faults:
1. Shard 4 of 6 ran out of its 230 minutes at 15,308 of 16,196 mutants (888 not run: evidence 469,
   identity/authz 419). Line count balances the files, not the mutants that have tests, and shard
   4 had the most (7,309 decided against 5,000 to 6,000 elsewhere).
2. The floors job wrote the whole survivor list (4.4 MB) to the job summary, over GitHub's 1 MiB;
   the step summary upload was aborted.

## Plan
- Tests for functions no unit test reached ("No tests" in the run), pure or with the database
  faked at the module's own seams (`tenant_session`, `names_of`, `audit_labels`, `index_batch`):
  - `tests/unit/audit_trail/test_labels_behaviour.py`: the label index (G-02-T10).
  - `tests/unit/audit_trail/test_values_and_metrics.py`: the values gate (G-02-T09) and the pilot
    metric reads (Q-04-T006).
  - `tests/unit/evidence/test_firm_export_archive.py`: the firm export's archive bytes (Q-02-T43,
    Q-02-T47).
  - `tests/unit/evidence/test_export_views_and_holds.py`: the export and firm export contract
    shapes, the grant digest, the INV-1 human check, legal holds' view and coverage.
  - `tests/unit/evidence/test_files_helpers.py`: FIL folder refs, virtual splits, folder listing,
    tree nodes, the access log's actors.
- `WEEKLY_SHARDS = 8`; the workflow's matrix, `--shards 8` and `/8` follow; the two tests that
  name the count follow it.
- The floors job writes only the table to the job summary; every survivor stays in the
  `mutation-weekly` artifact.
- Rollback: revert the commits; nothing in product code changes.

## Progress log
- 2026-11-13: run 43284162288 read (artifacts in the session scratchpad). 75 evidence and 52
  audit_trail tests written; ruff, pyright, banned patterns and the floors guard clean; 645 tests
  in the touched directories pass.
- 2026-11-13: local mutmut 3.8.0 over the nine files, narrowed in a scratch copy (only_mutate the
  nine files; tests from tests/unit/audit_trail and tests/unit/evidence only, so a lower bound):

  | File | Run 43284162288 killed | Local killed | Local survived |
  |---|---|---|---|
  | audit_trail/labels.py | 0 | 304 | 17 |
  | audit_trail/metrics.py | 0 | 118 | 2 |
  | audit_trail/values.py | 0 | 87 | 5 |
  | evidence/export_contract.py | 0 | 75 | 8 |
  | evidence/exports.py | 0 | 60 | 1 |
  | evidence/files.py | 0 | 178 | 14 |
  | evidence/firm_export_activities.py | 0 | 208 | 13 |
  | evidence/firm_export_contract.py | 0 | 55 | 7 |
  | evidence/holds.py | 0 | 164 | 15 |

  audit_trail +509 killed: about 26% against its 14% floor. evidence +740: about 23.0% against
  22% (22.7% if all 469 mutants shard 4 never reached survive).
- 2026-11-13: rebased on main f2a76b4aa (S39, S40), tests re-run. Weekly run dispatched on the
  branch to measure (see the PR).
- 2026-11-13: run 43330118713 (eight shards) confirms: the floors job passes. audit_trail 26.1%
  (floor 14%, 1,034 killed), evidence 23.6% (floor 22%, 9,093 killed, none not run). Every scope
  meets its floor: agents/runtime 19.3, ai_gateway 27.8 (20), assurance/release_archive 14.6,
  compute 74.1, identity/authz 69.6 (62), kernel/crypto 70.0 (53), kernel/db 22.6 (13),
  kernel/realtime 62.7, kernel/uow 6.7 (2), review 4.8, signatures 8.3, tax/individual 52.8.
- 2026-11-13: shard 4 of 8 still ran out at 11,830 of 12,178 (348 identity/authz mutants not run).
  Cause measured from its .meta durations: `identity/authz/__init__.py` cost 480 CPU minutes for
  1,242 mutants (20.3 s a line; no other file in the shard over 1.4 s a line), since nearly every
  unit test calls `authorise`; with it, mutmut's stats and clean passes took 97 minutes before the
  first mutant. Alone in a shard it would still need about 160 minutes of mutants after that, over
  the 230-minute budget, so a weight alone does not fix it: its mutants need splitting across two
  shards (by function name, `mutmut run <names>`) with the shards' .meta files merged per file.
  Proposed as its own task; not built here.
- 2026-11-13: AY approved the ratchet. `backend/mutation-thresholds.yaml` raised to the run's scores
  rounded down, identity/authz kept at 62 (DEC-4817); the floors guard passes.

## Rows
- Q-03-T072 (ai_gateway and audit_trail meet their floors): done (run 43330118713: 27.8% of 20%,
  26.1% of 14%).
- Q-03-T147 (no red module below its floor; floors ratcheted): done. No red module is below its
  floor (run 43330118713), and the floors ratchet to that run (AY approved; DEC-4817). identity/authz
  stays 62 until a run decides all its mutants (the authz shard split, its own task).
- Q-03-T179 (every compute package 85% killed): not met. compute is 73.6% overall; a per-package
  split is in the run's survivors list. Left todo.
- Q-03-T180 (review, signatures, integrations, consents meet floors): review and signatures meet
  their 0% floors; integrations and consents are not mutation scopes. Left todo.
- Q-03-T227 (each compute package meets its floor): done. compute is 74.1% of a 0% floor.

## Decisions made during this task
DEC-4815, DEC-4817.
