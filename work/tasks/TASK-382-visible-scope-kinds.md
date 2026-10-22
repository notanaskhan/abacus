---
id: TASK-382
title: Generalised visible() - scope kinds engagement, work_item, client, client_entity, portal_scope (F-03-T27)
spec: SPEC-002
acceptance_criteria: [AC-4]
risk_zone: red
status: done
epic: F-03
plan_key: F-03-T27
branch: f03-t27-visible-scopes
created: 2026-10-22
updated: 2026-10-22
---

## Objective
"Lena Park gets 404 for Ashford through every scope kind, and the property test passes for all
five kinds." (ADR-145, P-06)

## What changed
- `identity.authz.visible_scope(ctx, action, scope, column, *, grant_kind=None)`: `engagement`
  and `work_item` read through `visible()`; `client` and `client_entity` admit a client when a
  firm role allows the action or the person may read at least one of its engagements (through
  `register_clients_of_engagements`, registered by engagements), and exclude walled clients on
  `client_id`; `portal_scope` matches the client user's active grants of `grant_kind`. An
  unregistered lookup admits nothing.
- LIST-001 accepts `visible_scope` and requires a literal scope kind.
- Tests: `tests/unit/identity/test_visible_scope.py` (filters per kind, fail closed) and
  `tests/integration/test_visible_scope_kinds.py` (Lena walled from Ashford across the four
  firm kinds, a walled firm admin, a portal scope; each compared with `authorise` or the grant).

## Progress log
- 2026-10-22: built. Tests run in the batch's end-of-run CI (S3 batch rule).
- 2026-10-22: fixed `tests/integration/test_visible_scope_kinds.py`. `_listed` passed an unbound column to `visible_scope`, which correlated with the wall subquery ("more than one row returned by a subquery"), and 5 of the 9 cases failed. The columns are now bound to the table, and all 9 pass. Found by F-03-T33. Product code was unaffected: repositories pass table columns.
