---
id: TASK-1015
title: Escaped defects ED-009 (security_admin in the staff models) and ED-011 (three gate facts in the human-only register) — migration 0127
spec: SPEC-024
acceptance_criteria: [AC-3, AC-4]
risk_zone: red
status: done
epic: Q-03
plan_key: Q-03-T006; Q-03-T008
branch: s6-defects-ed009-ed011
created: 2026-10-24
updated: 2026-10-24
---

## Objective
Fix the two SEV3 escaped defects the S6 back-fill found (`docs/quality/escaped-defects.md`), each held by `xfail(strict=True)` tests, and lift those markers without changing the tests otherwise.

- **ED-009** (SPEC-024 AC-3, AC-4; P-10, DEC-21): a firm with a `security_admin` member answers 500 on `GET /v1/firm/staff`, and inviting or changing someone to it answers 422. Tests: the three `_P10` tests in `backend/tests/integration/backfill/test_staff_people.py`.
- **ED-011** (SPEC-025 §14; INV-1, Q-02-T17): `engagement.acceptance_recorded`, `engagement.letter_recorded` and `independence.declined` are not in the human-only register, so the database would accept them audited as the agent. Tests: the three `_NOT_REGISTERED` cases of `test_ac4_the_database_refuses_a_gate_fact_audited_as_the_agent` in `backend/tests/integration/backfill/test_acceptance_independence_letter.py`.

## Plan (red zone)
- **ED-011 register:** add the three actions to `docs/architecture/human-only-actions.yaml` (verbs `accept`, `confirm`, `decide`), regenerate `kernel/_human_only_actions.py` (`abacus_tools.codegen.human_only_actions`). The database's `abacus_human_only_actions()` is defined by the last migration that changed the list (0097), so migration **0127** redefines it with `CREATE OR REPLACE` (keeps 0098's EXECUTE grant; the trigger needs no change). The drift test `test_human_only_guard.py` holds the YAML, the module and the function together.
- **ED-009 contract:** `identity/routes.py` `StaffRole` gains `security_admin` (the four roles of `staff.FirmRole`), then `make regenerate`. `staff._ROLE_INDEX` gains `security_admin: 4`, so `membership.role_changed` does not record it as "no firm role" (0).
- **ED-009 database:** the 0033 definer functions `add_staff_membership` and `membership_set_firm_role` hard-code the three SPEC-024 roles (`not a firm role`), so accepting a `security_admin` invitation or changing to it answers 500 even with the models fixed. 0127 also redefines both with the four roles of 0080's check constraints (bodies otherwise unchanged; `CREATE OR REPLACE` keeps owner, `SECURITY DEFINER` settings restated, grants kept). Both are already registered in `schema_check.py`.
- **Frontend:** `legacy/FirmPeople.tsx` takes its role type from the generated `StaffMemberOut` and lists `security_admin` as "IT / Security" (glossary), so the member is not shown as "Team member"; `fixtures/seed/people.ts` `FIRM_ROLES` type widened; a `spec024people.test.tsx` case for the new option.
- **Docs:** ED-009 and ED-011 `fixed` in `docs/quality/escaped-defects.md`; `docs/quality/backfill.md` row 041; DEC-230.
- **Rollback:** `alembic downgrade 0115` restores the three-role functions and the 0097 list; revert the commits.

## Progress log
- 2026-10-24: ED-011 fixed: register, generated module, migration 0127; the three `_NOT_REGISTERED` cases pass without their marker.
- 2026-10-24: ED-009 fixed. Lifting the models alone left two tests failing with 500: 0033's `add_staff_membership` and `membership_set_firm_role` raise `not a firm role` for `security_admin`, so 0127 (renamed `0127_gate_facts_and_security_admin.py`) redefines both too. Frontend types and the People page follow the generated client. DEC-230.
- 2026-10-24: verified. Integration: `backfill/test_staff_people.py`, `backfill/test_acceptance_independence_letter.py`, `test_human_only_guard.py` 93 passed, 1 xfailed (ED-010, untouched); `test_identity.py`, `test_schema_check_db.py`, `backfill/test_signup_and_engagement_types.py` 379 passed. `tests/unit tests/contracts tests/security`: 25096 passed, 6 failed; the same 6 fail without this change (`unit/identity/test_independence.py` x2, `unit/identity/test_permission_matrix.py` x3, `contracts/c5_requests_binders/test_c5_consumer_r01.py` x1, all `visible()` client-grant SQL shape, after DEC-211). Web: tsc clean, vitest `src/legacy src/status src/fixtures` 681 passed. `make check-fast` green.
