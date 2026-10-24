---
id: TASK-1140
title: S7 pen-scope security files and independent AC suites (Q-03-T012, T013, T014, T015; Q-02-T36; P-04-T13; P-06-T17; P-01-T15; F-04-T36)
spec: SPEC-002
acceptance_criteria: [AC-4, AC-5, AC-7]
risk_zone: red
status: in-progress
epic: Q-03
plan_key: Q-03-T012; Q-03-T013; Q-02-T36; P-04-T13; P-06-T17; P-01-T15; F-04-T36; Q-03-T014; Q-03-T015
branch: s7-security-tests
test_author: ayushkbhatia
test_session: 2026-10-24, branch s7-security-tests (one clean session per suite, following .claude/skills/ac-test-author/SKILL.md)
created: 2026-10-24
updated: 2026-10-24
---

## Objective
- **Q-03-T012:** "The file is a required check by Fri Feb 12, 2027 and fails on a seeded wall bypass in each of the seven surfaces."
- **Q-03-T013:** "Each hostile sample is refused or quarantined with the documented status and none reaches preview or extraction."
- **Q-02-T36:** "The suite fails against seeded violations of I-RETENTION-FLOOR and I-HOLD and passes on main."
- **P-04-T13:** "AC tests pass and fail when any human-only CHECK or insert-only trigger is removed, and the Undo conformance suite fails for a route that skips the window or the grant void."
- **P-06-T17, P-01-T15, F-04-T36, Q-03-T014, Q-03-T015:** as their rows.

## Plan (red zone; tests only)
- **Files:** `backend/tests/security/test_walls_and_need_to_know.py` (T012), `backend/tests/security/test_upload_hostile_files.py` (T013), then one independent file per remaining row.
- **Migrations, registry, flags:** none. Product code changes only where a test exposes a small local defect, each logged in `docs/quality/escaped-defects.md`; anything larger is held with `xfail(strict=True)` citing this task.
- **Boundary:** `create_app()` over HTTP on the migrated testcontainer Postgres, seeded as the superuser; public `api.py` functions where a row names one. Expectations from specs, contracts, ADRs and decisions only (ADR-078).
- **Rollback:** delete the test files; revert the logged fixes.

## Q-03-T012: walls and need to know
Seven surface probes (records, lists, search, counts, notifications, exports, agent sessions), each returning what it found of Ashford for Lena Park; the holding tests assert none, with Granite as the control. Plus two sweeps over the served route table (every GET naming Ashford's engagement, client, version or run reads exactly as an id that never existed; no list route carries Ashford), ADR-024 metadata-only for an off-team admin and `security_admin`, a walled admin, and `test_d1_a_seeded_wall_bypass_fails_every_surface` (the wall lifted in the database; every probe must report Ashford). 61 tests, all pass.

- **Defect ED-017 (fixed):** every trace export answered 500. C6 §7 records `Ref(sha256, rows)` and the unit of work's `Ref` refused a key containing a digit; nothing on `main` had ever exported a trace. `Ref` keys may now carry digits after the first letter (`kernel/uow/__init__.py`).
- **Noted, not a defect:** the C4 viewer family (`/v1/evidence-versions/{id}/viewer`, `/search`) is a contract stub answering 501 before any authorisation when `evidence.viewer_v1` is on; it reads the same for a walled id and an unknown one, so the sweep passes. The live viewer (P-03) must authorise first; the sweep will hold it to that.

## Progress log
- 2026-10-24: T012 written and green (61 passed); ED-017 fixed with it.
