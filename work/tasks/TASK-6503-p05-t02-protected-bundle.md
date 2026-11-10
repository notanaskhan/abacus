---
id: TASK-6503
title: "P-05-T02: protected bundle — collaboration and audit_trail matrix rows, two flags, edges, glossary, AUD-29 501 stubs"
spec: SPEC-650
acceptance_criteria: [AC-36, AC-39]
risk_zone: red
status: in-review
branch: s33-p05-t02
worktree: /Users/ayushkbhatia/Accrued/abacus-s33
created: 2026-11-09
updated: 2026-11-09
plan_key: P-05-T02
---

## Objective
P-05 §4.10's protected bundle, so T03 to T14 build against registered actions, flags and edges.

## Plan (red: files, registries, tests, rollback)
1. `docs/architecture/permission-matrix/collaboration.yaml` (new): `comment.resolve`, `todo.read`,
   `todo.create`, `todo.update`, `todo.complete`, `todo.assign`, `todo.delete`; agent, client roles,
   `client_service`, firm admin and platform support denied.
2. `audit_trail.yaml`: `audit_event.read_engagement` (OQ-1 readers; firm admin denied).
   `requests.yaml`: `eqr_reviewer` and `specialist` on `comment.read` and `comment.create` (DEC-21;
   P-05 §4.4 says T02 adds them if missing; it also reaches the live request-item threads).
3. Flags `collaboration.v2` (new `feature-flags/collaboration.yaml`) and
   `audit_trail.engagement_activity` (boolean, default false, DEC-137 override as every 2026 flag).
4. Status objects `todo` and `comment_thread` already exist in `status-vocabulary.yaml` (F-03).
5. Glossary rows: Comment thread, Anchor kind, Thread comment, Correct…, Redact….
6. `MODULE_DEPENDENCIES`: collaboration += review, communications; workpapers += collaboration.
7. `audit_trail/engagement_activity_contract.py`: the two AUD-29 routes, principal → engagement →
   action → flag, 501.
8. Regenerate `_matrix.py`, `actions.gen.ts`, `_flags.py`, generated security tests.
Rollback: revert the commit; no migration. TABLE_OWNERS entries land with the tables (P-05-T04).

## Progress log
- `2026-11-09` — Built. Tests generated (allow/deny, fresh MFA, route introspection), not run (end
  pass). Plan dates (flags created Tue Jan 25, 2028, expiring Apr 24, 2028) map to the 2026 build
  clock as every S32 flag does (created today, DEC-137's 180 days).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-3103 | P-05's matrix rows, flags and edges; EQR and specialist on the live comment actions | no |
