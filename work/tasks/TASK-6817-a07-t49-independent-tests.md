---
id: TASK-6817
title: "A-07-T49: independent AC and property tests (ADR-078) for T30, T31, T36, T37 and T42"
spec: SPEC-644
acceptance_criteria: [AC-5]
risk_zone: red
status: in-review
branch: s36-a07-t49
worktree: /Users/ayushkbhatia/Accrued/abacus-s36
created: 2026-11-11
updated: 2026-11-11
plan_key: A-07-T49
---

## Objective
Tests written apart from the builders of A-07-T30, T31, T36, T37 and T42 fail if a release can be
recorded with any gate unmet or if a locked row changes.

## Plan (red)
- Files: `backend/tests/unit/assurance/test_a07t49_independent.py`,
  `backend/tests/integration/test_a07t49_locked_rows.py`.
- Gap found by the tests and fixed here (DEC-3411): `archive.lock` carried no `mfa_recent` and was
  missing from `fresh-mfa-actions.yaml`, although the contract (`audit-completion.md`, "Lock
  (human only, fresh MFA)") and DEC-2231/2261 attach it with T37's live handler. `decide_lock`'s
  own `fresh_mfa_at` landed on main with TASK-6881 (taken on restack). Now: the matrix cell
  (`permission-matrix/assurance.yaml`, regenerated `_matrix.py` and
  `tests/security/test_fresh_mfa_generated.py`) and the fresh-MFA list.
- No migration, no flag. Rollback: revert the commit (the lock would again accept a stale factor).

## Covered
- G8: any unmet G5/G6/G7 is a blocker (property); refused at the request, at the workflow's
  re-check after the grant is consumed, and before the one unit of work opens; a changed snapshot
  with every gate met is refused; a failure inside the unit escapes it (rollback) and records
  nothing; replay with the same key answers the stored release, another key is refused.
- F7: the nine items in order; any one item flipping moves the checklist hash (property); the
  lock refused at 8 of 9 (each item), on an unseen checklist, when locking or locked, and with a
  stale or missing factor; the binder is always A to H and a failing provider is not counted;
  the index hash moves with any count (property).
- Clocks: 60-day goldens (47 days on Oct 22, at risk from 7, due today, overdue, leap and
  non-leap February), stopped when locked, the five timers, state by days left (property); the
  five-year floor (property, Feb 29 to Feb 28) and its database CHECK.
- Seal: byte-identical whatever the read order (property), any changed leaf moves it (property),
  empty binder, canonical bytes, no floats, seal = SHA-256 of the body; COMPLIANCE manifest until
  the floor and GOVERNANCE evidence until retention.
- Additions: only the EP approves; agent and system refused before any read; the adder never
  approves; a decided addition is never decided again; additions need a locked archive.
- Matrix: the agent and the system are denied report.release, archive.lock and
  archive_addition.approve, each with fresh MFA.
- Postgres: a locked archive row never changes (status, seal, retention either way, records key,
  locker) nor is deleted; the lock decision, the manifest and the binder index never change.

## Progress log
- `2026-11-11` — Built (S36). Tests written, not run (end pass). Gap fixed: archive.lock fresh MFA
  (DEC-3411). The record-mode completion route (`completion.py`, `archive.lock`) now also needs a
  fresh factor; check its tests at the end pass.
