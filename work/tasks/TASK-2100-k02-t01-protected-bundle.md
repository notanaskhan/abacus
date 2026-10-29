---
id: TASK-2100
title: K-02-T01 S16 protected bundle for K-02
spec: SPEC-500
acceptance_criteria: [AC-1, AC-2, AC-3]
risk_zone: red
status: in-review
epic: K-02
plan_key: K-02-T01
branch: s16-k02-t01
created: 2026-10-29
updated: 2026-10-29
---

## Objective
The matrix rows, the `owner_of_target` condition, the two flags and the fresh-MFA listings K-02
needs before any of its routes exist (K-02 §4.4, §4.8, §4.9).

Acceptance (backlog row): "The bundle merges first in the S16 batch, and the generated permission
tests deny the agent, portal principals and a non-owner partner every K-02 write."

## Plan (red)
- `docs/architecture/permission-matrix/methodology.yaml`: `firm_standard.read/create/assign_owner/
  draft/import/publish`; `platform.yaml`: `reference_set.read`; `practice.yaml`: `due_date.read`.
- `identity/authz/matrix.py`: `owner_of_target` in `CONDITION_KEYS`, `_FLAG_CONDITIONS`, `Rule`.
- `identity/authz/conditions.py`: `ConditionFacts.owner`; a person's condition in `conditions_hold`.
- `identity/authz/__init__.py`: `TargetFacts.owner_user_id`; `has_conditions`; `_condition_facts`
  computes `owner` (the owner and `_partner_level` now; support never).
- `abacus_tools/codegen/security_tests.py`: `expected` denies without target facts; owner variants
  for the derived `firm_partner` cell; `firm_standard` writes join the resolution entities (agent,
  system and support denied). `tests/security/matrix_harness.py`: `owner`/`not_owner` variants and
  the firm-partner arrangement.
- Flags `knowledge.firm_standards`, `rules.reference_sets` (feature-flags/methodology.yaml,
  platform.yaml). Fresh-MFA register: `firm_standard.create`, `.publish` (group `standards`, added
  to both group lists).
- `make regenerate` (matrix, actions.gen.ts, _flags.py, generated security suites).
- Not here (DEC-1150): schema_check registries land with the migrations (T03, T04).
- Rollback: revert the branch; no table, route or data depends on it yet.

## Acceptance
| Check | Test |
|---|---|
| Agent, system and portal denied every write | `test_ac_every_k02_write_denies_the_agent_the_system_and_the_portal`; generated `NEVER` and matrix cases |
| Non-owner partner denied draft and publish | `test_us33_*`; generated `CONDITIONS` (`not_owner`) |
| Former partner owner denied | `test_an_owner_who_is_no_longer_a_partner_cannot_publish` |
| Reads for every firm role, agent at task scope | `test_every_firm_role_reads_and_the_agent_only_at_task_scope` |
| No reference-set write action | `test_there_is_no_reference_set_write_action` |
| Flags default off | `test_the_two_flags_exist_default_off_and_expire_inside_90_days` |
| Condition allow/deny meta-test | `tests/unit/identity/test_matrix_conditions.py` (owner cases) |

## Progress log
- 2026-10-29: built (S16 block; tests written first, run at the batch's end review). DEC-1150.
