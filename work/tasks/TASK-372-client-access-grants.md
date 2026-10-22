---
id: TASK-372
title: Client access grants, role-union portal scopes and scope_only (F-03-T26, expand step)
spec: SPEC-025
acceptance_criteria: [AC-1]
risk_zone: red
status: done
epic: F-03
plan_key: F-03-T26
branch: f03-t26-client-grants
created: 2026-10-22
updated: 2026-10-22
---

## Objective
"Meera Shah's grants yield a role-union shell limited to Meera's own scopes, and every former
client_admin/client_contributor row is an owner/contributor grant." (ADR-146)

## Plan (red)
- Migration 0083: `client_access_grants` (12 roles, 9 scope kinds, document classes, expiry,
  status; app updates status only), insert-only `client_access_events`; backfill every client
  `engagement_members` row as an owner/contributor engagement grant; an invoker trigger mirrors
  new, changed and deleted client rows (ADR-146's one release of dual-read).
- `identity/client_access.py`: `shell_of`, `portal_scopes`, `scope_covers` (registered as the
  `scope_only` lookup), `grant_client_access` / `revoke_client_access` behind new actions
  `client_access.grant` / `.revoke`, with events `client_access.granted`/`.revoked` and
  `access.changed`.
- engagements registers the `work_item` and `client` scope resolvers; other kinds fail closed
  until their owners register.
- DEC-129. Rollback: revert, downgrade 0083.

## Definition of done
- [x] `tests/unit/identity/test_client_access.py`: shells, story 5.2 coverage, fail closed
- [x] `tests/integration/test_client_access_grants.py`: backfill down/up on a private database,
  the mirror, Meera Shah on Postgres
- [x] Backend unit, acceptance, security, schema suites; `make check-fast`

## Follow-up
TASK-373, the contract step: authorise's client roles and every client-hub read from grants,
`engagement_members` CHECK narrowed to staff roles, the mirror dropped.

## Progress log
- 2026-10-22: expand step built and merged.
