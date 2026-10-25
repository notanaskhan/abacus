---
id: TASK-1196
title: Team, acceptance, independence and conflict contract stubs (engagements and organisations) (P-07-T29)
spec: SPEC-332
acceptance_criteria: [AC-1, AC-6, AC-10, AC-17, AC-18, AC-20, AC-24, AC-25]
risk_zone: red
status: done
epic: P-07
plan_key: P-07-T29
branch: s8a-team-roles
created: 2026-10-25
updated: 2026-10-25
---

## Objective
"Every human-only action denies agent and system in the generated matrix tests from the stub onward" (P-07-T29). Contract first for ENG-05, CLI-07, CLI-08 and CLI-06's conflict and screening rows (P-07 §4.3, §4.4).

## Plan (red zone)
- **Code:** `engagements/acceptance_contract.py` *(new)*: classified models and routes for acceptance (read, answers, flags, manual checks, send to partner, conditions, risk-partner review, decision), independence (summary, rotation, confirm, decline, reminders, NAS, breaches, conclude), the ENG-05 team rows (approval, portal visibility, EQR candidates, assign, eligibility approval). `organisations/conflicts_contract.py` *(new)*: conflict checks (run, read, clear) and screening records. Each route has one matrix action; acceptance, independence and conflict routes answer 404 with `engagements.acceptance_v2` off and 501 on; the ENG-05 team routes answer 404 with `engagements.v2` off and 501 on until P-07-T30.
- **Matrix (protected):** `engagements.yaml` gains `acceptance.read/prepare/request_review/decide`, `independence.read/remind/conclude/breach_manage`, `nas.evaluate`, `team.approve`, `eqr.assign`, `eqr.approve_eligibility`; `independence.confirm` gains explicit agent and system deny. `organisations.yaml` gains `conflict.run`, `conflict.clear`, `screening.record`. Every decision and confirmation denies agent and system (I-AGENT-NEVER); no client role holds any.
- **Flag:** `engagements.acceptance_v2` (`expires: 2027-04-21`, `override: DEC-137`).
- **Errors:** `decision_locked`, `rationale_required`, `acceptance_not_ready`, `review_required`, `independence_preconditions_unmet`, `not_self`, `eqr_on_team`, `eqr_approver_is_ep`, `eqr_not_eligible` (`error_codes --write`).
- **Docs:** `docs/contracts/acceptance-independence.md`, register row in `docs/contracts/README.md`, DEC-326.
- **Tests:** `tests/contracts/acceptance_independence/test_acceptance_independence_stub.py` (actions, 404 and 501, option sets, redacted conflict row shape, classification, agent and system denied, flag gate); closed lists (`test_app_gates.py` 201 and 200 lists); `make regenerate` (client, `_flags`, `_matrix`, generated security tests, route introspection).
- **Rollback:** revert the commit; no migration.

## Progress log
- 2026-10-25: built as planned: 29 routes (25 engagements, 4 organisations), 15 new matrix actions, `engagements.acceptance_v2`, nine error codes, the contract doc and register row, DEC-326. `make regenerate` and `error_codes --write`. `tests/contracts` 3,284 passed, 4 xfailed; `tests/unit/quality`, the generated matrix and resolution suites, the status-vocabulary conformance and app-gate tests green.
- 2026-10-25 (final checks on the branch): `uv run pytest tests/unit tests/contracts tests/security` 29,446 passed, 5 xfailed, 1 failed: `tests/unit/synthetic/test_generate.py::test_ac17_default_generation_and_exports_finish_within_five_seconds`, a 5-second timing test on a machine at load 16; the file passes alone (45 passed). Integration (targeted): 19 files incl. G2 v2, work items, engagements v2 live, drafts, human-only guard, assurance phase and the engagement/independence back-fills (`test_independence_gate.py`, `test_due_dates_and_delegation.py`, `test_p07t26_contacts_g2_independent.py` and others) 341 passed, 5 xfailed; earlier on the branch `test_engagements.py`, `test_engagements_schema.py`, `test_schema_check_db.py`, `backfill/test_team_management.py` 506 passed (the two C1 team-shape failures fixed and rerun green), `test_team_roles.py` + `test_engagement_hold.py` 12 passed. `make check-fast` green; web `tsc` clean; vitest `src/status`, `src/fixtures/contracts` 180 passed, ENG-02 26, legacy people and POR-02 22.
- 2026-10-25 (security review round): fixes recorded in DEC-326 to DEC-328 (one commit, failing tests first); see the TASK-1197 entry for the test runs.
