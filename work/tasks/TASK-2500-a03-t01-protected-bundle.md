---
id: TASK-2500
title: A-03-T01 S20 protected bundle for A-03
spec: SPEC-580
acceptance_criteria: [AC-1, AC-2, AC-3]
risk_zone: red
status: done
epic: A-03
plan_key: A-03-T01
branch: s20-a03-t01
created: 2026-10-30
updated: 2026-10-30
---

## Objective
The matrix rows, flags, fresh-MFA listing, dependency edge, glossary rows and protected-path
entries A-03 needs before any of its S20 routes exist (A-03 §4.3, §4.6, §4.7).

Acceptance (backlog row): "The bundle merges first in the S20 batch, generated tests deny the
agent, support and portal principals every A-03 write, and import-linter rejects a compute import
of any module."

## Plan (red)
- `permission-matrix/sampling.yaml`: `population.read/create`, `sample_set.read/approve/export/
  generate_requests`; `sample_set.create` denies agent and system explicitly.
- `permission-matrix/assurance.yaml`: `grouping_set.read`, `mapping_set.read/run/confirm`,
  `account_mapping.edit`; explicit agent/system deny on `grouping_set.import/publish` and
  `mapping_set.edit` (kept for the live SPEC-316 routes until T08).
- `fresh-mfa-actions.yaml`: `grouping_set.publish` (group `standards`).
- Flags: `feature-flags/sampling.yaml` `sampling.sample_sets`; `feature-flags/assurance.yaml`
  `ledger.tb_mapping`.
- `banned_patterns.MODULE_DEPENDENCIES`: `sampling` += methodology, review, requests.
- `docs/product/glossary.md`: Population, Completeness tie, Sample stratum, Account mapping.
- `docs/architecture/protected-paths.md`: sampler compute and the frozen corpus.
- `make regenerate` (matrix, actions.gen.ts, _flags.py, generated security suites).
- Not here (DEC-1550): schema registries with the migrations (T05); the import-linter contract
  with the kernel modules (T21).
- Rollback: revert the branch; no route, table or data depends on it yet.

## Acceptance
| Check | Test |
|---|---|
| Agent, support and portal denied every write | `test_ac1_every_a03_write_denies_the_agent_support_and_the_portal`; generated matrix and resolution suites |
| System holds no write but the run start | `test_ac1_the_system_holds_no_a03_write`, `test_ac1_the_system_only_starts_a_mapping_run` |
| Reads: the team; the agent at task scope | `test_ac1_reads_are_the_teams_and_the_agent_only_at_task_scope` |
| Approve never the preparer; publish fresh MFA | `test_ac2_*`; generated `test_fresh_mfa_generated.py` |
| Flags default off; dependency edge acyclic | `test_ac3_*` |

## Progress log
- 2026-10-30: built (S20 block; tests written first, run at the batch's end review). DEC-1550.
