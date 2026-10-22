---
id: TASK-369
title: Matrix conditions (level_in, function_in, not_offshore, attest_client, gates_met, scope_only, in_scope) and actions.gen.ts (F-03-T24, part 1 of 2)
spec: SPEC-025
acceptance_criteria: [AC-7]
risk_zone: red
status: in-progress
epic: F-03
plan_key: F-03-T24
branch: f03-t24-conditions
created: 2026-10-22
updated: 2026-10-22
---

## Objective
"Generated allow and deny tests exist for every new condition, and a property test proves no firm
override widens the matrix ceiling." This part: the conditions and their generated tests. Part 2
(TASK-370): firm_settings, stricter-only firm_policy_overrides and their property test, DEC-38.

## Plan (red)
- `authz/matrix.py` parses the condition keys on an action (`level_in: "partner,manager"`,
  `function_in`, `not_offshore: required`, `attest_client: deny|only`, `gates_met: "G5,G6"`,
  `scope_only: required`) and keeps each role's `firm_setting(<name>)`; unknown values are an
  import error.
- `authz/conditions.py`: `conditions_hold(rule, facts, person=…)` (pure) and the lookups the
  owners register (functions, gates, service line from engagements; attest flag from
  organisations, F-03-T25; client scopes from the grants, F-03-T26). A condition without facts
  denies.
- `authorise`: layer 3c after independence; agents and system runs are held to the resource
  conditions (attest, gates), their initiator to the actor ones. `in_scope` resolves to allow for a
  practice leader or quality partner whose service lines include the engagement's (DEC-126), and
  only when no other role's allow or deny already decides. `visible()` refuses an action with
  conditions (fail closed). `Resource.work_item_id`.
- `identity.repository.member_facts`; engagements registers its three lookups.
- `actions.gen.ts` (apps/web/src/app-core) from the matrix codegen, in the drift check.
- No action uses a new condition yet, so no grant changes. Rollback: revert.

## Definition of done (part 1)
- [x] `tests/unit/identity/test_matrix_conditions.py`: an allow and a deny case per condition
  (generated from one table, with a meta-test), fail-closed cases, agents and runs, `in_scope`
- [x] Backend unit and acceptance (15,275), security and engagement integration (456)
- [x] `make check-fast`
