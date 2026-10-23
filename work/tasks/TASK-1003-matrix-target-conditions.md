---
id: TASK-1003
title: Matrix condition types not_preparer_of_target and reserved_role, generated allow and deny tests, I-AGENT-NEVER for every P-04 resolution action (P-04-T15)
spec: SPEC-308
acceptance_criteria: [AC-5]
risk_zone: red
status: done
epic: P-04
plan_key: P-04-T15
branch: s6-review-integrity
created: 2026-10-24
updated: 2026-10-24
---

## Objective
"Generated tests deny the agent, system and support principals every sign-off, decision, proposal, checkpoint and issue-resolution action, and deny a preparer the L2 action on their own target." (P-04-T15.)

## Plan (red zone)
- **Parser (`identity/authz/matrix.py`):** `not_preparer_of_target: required` and `reserved_role: required` join `CONDITION_KEYS`; `Rule` gains both flags; anything else is an import error.
- **Facts (`identity/authz/__init__.py`):** `Resource.target: TargetFacts(preparer_user_ids, reserved_role, reserved_user_id)`, put there by the owning service. `_condition_facts` resolves `preparer` and `reserved_holder` for a person (never for a support session); `_holds_reserved`: the named person, holding the engagement role (or the `signer` function on the work item). Missing facts deny.
- **Evaluation (`conditions.py`):** target conditions are a person's: an agent or a system run never meets them.
- **Matrix (`review.yaml`):** `sign_off.review`, `sign_off.manager` + `not_preparer_of_target`; `decision.decide` + `reserved_role`; DEC-145's reviewer and preparer function narrowings (`checkpoint.approve/reject/restore`, `issue.verify/reopen`: reviewer functions; `field.edit`: `preparer`).
- **Callers:** `review.service.record_sign_off` builds the target facts (the owner's `ReviewableFacts` preparers and the current L1 signers) and answers a preparer's condition denial as 409 `preparer_cannot_review` (the legacy screens show that code); `assurance.dashboard` asks `could(sign_off.review)` per paper with its preparer.
- **Codegen (`abacus_tools/codegen/security_tests.py`):** `expected()` denies the target conditions without facts; new generated `tests/security/test_resolution_actions_generated.py`: every resolution action × {agent, system, support} denied, and each target condition's allow and deny cases for every role its row allows. Harness: `tests/security/matrix_harness.py` (`condition_outcome`, `principal_outcome`).
- **No migration, route or flag.** Rollback: revert the commit and `make regenerate`.
- **Tests:** generated suite; `tests/unit/identity/test_matrix_conditions.py` cases for both keys plus person-only and reserved-role rules; `tests/integration/test_sign_off_segregation.py` (a preparer is refused L2 and L3, another reviewer signs); suites testing other layers on every allowed pair meet the condition facts (`conditions_met` fixture).

## Progress log
- 2026-10-24: built as planned. Generated: 84 I-AGENT-NEVER cases (28 actions × 3 principals) and 27 condition cases.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-216 | Target facts on the resource, person-only conditions, the `signer` reservation, the 409 kept for preparers, DEC-145's narrowings, what counts as a resolution action | No (ADR-160, ADR-005) |
