---
id: TASK-2533
title: T-02-T30 security suites for delta #2 (K-1 room and POR-05)
spec: SPEC-502  # AC-1, AC-5; T-02 §3.5 to §3.8
acceptance_criteria: [AC-1, AC-5]
risk_zone: red
status: in-review
epic: T-02
plan_key: T-02-T30
branch: s20d-t02-t30
worktree: /Users/ayushkbhatia/Accrued/abacus-s20b
created: 2026-11-01
updated: 2026-11-01
---

## Objective
Security suites for delta #2: K-1 recipient, role-union and inquiry-addressee cases in
test_portal_scope_isolation.py, K-1 and organizer fields in test_tri_and_offshore.py and
test_classification_scrubbing.py; delta #2 build pinned to the Thu Jul 29, 2027 train build (as
T-01) with the K-1 room and POR-05.

Acceptance (backlog row): "The suites are required checks before Mon Aug 2, 2027 and fail on a
planted cross-scope K-1 read."

## Plan (red: tests only)
- `tests/security/test_portal_scope_isolation.py`: a K-1 recipient reads only their own released
  package (another recipient's, a granted draft and an unknown id answer 404 and name nothing);
  the role union's K-1 names nothing of the issuing return; an inquiry is its addressee's only;
  the judgement fails on a planted cross-scope K-1 read.
- `tests/security/test_tri_and_offshore.py`: K-1 amounts and organizer answers are TRI, rows carry
  neither amounts nor a TIN; an offshore reader of a K-1 detail gets the TIN null.
- `tests/security/test_classification_scrubbing.py`: a K-1 box line and an organizer answer given
  to the logger never show their values.
- Stacked on T-02-T27 (`issuer_name`, the portal detail's TIN). Rollback: revert the additions.

## Notes
- "Required checks before Mon Aug 2, 2027" and the train-build pin are branch protection and
  release settings, a human step (the security workflow already runs `tests/security`).

## Progress log
- `2026-11-01` — Written on `s20d-t02-t30` (stacked on `s20d-t02-t27`); the DB-free cases pass;
  the Postgres cases run in the end review.
