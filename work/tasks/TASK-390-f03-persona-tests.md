---
id: TASK-390
title: Independent persona AC tests for roles, conditions, overrides, client record, grants and visible() (F-03-T33)
spec: SPEC-002
acceptance_criteria: [AC-4]
risk_zone: red
status: done
epic: F-03
plan_key: F-03-T33
branch: f03-t33-persona-tests
created: 2026-10-22
updated: 2026-10-22
---

## Objective
"Walled, offshore, client_service and role-union personas each have allow and deny cases that
pass on main." Written from F-03 §3.4-§3.6 (stories 4.1-4.3, 5.1, 5.2, 6.1), chapter 03
§4.4-§4.5, ADR-145/146/147 and DEC-126..129, not from the code (ADR-078).

## What changed
- `backend/tests/acceptance/test_f03_personas.py` (unit, in-memory firm, no database; 55 cases):
  - Walled, Lena Park ✕ Ashford: every matrix action on Ashford denied at the wall layer (404),
    Ashford's work item too, no capabilities offered; on Granite her preparer work is allowed and
    manager-only actions still deny at the role layer.
  - Offshore: `tin.reveal` parsed as chapter 03 §4.4 / DEC-52 declare it (`not_offshore`,
    `mfa_recent`, `requires: reason`; the real row lands with P-07-T04/T10). An offshore manager
    is refused at the condition layer and never offered it; the same manager onshore reveals;
    offshore keeps ordinary work; missing membership facts fail closed. A guard holds every
    `*.reveal*` action in the matrix to `not_offshore`.
  - client_service, Grace Holloway on Copperleaf: binders (`request_item.create/update`),
    invitations (`client_contact.invite`) and request status (`request_item.read`) allowed;
    evidence, comment and workpaper content denied at the role layer; capabilities agree; without
    `client_service` her firm role runs no binder. `security_admin` holds no content action.
  - Role union, Meera Shah: shell "full" with the K-1 scope listed, own 1040 covered, Ridgeline's
    return and engagement never covered, no matrix role on Ridgeline's engagement; K-1-only gets
    "k1", a third party "limited", no grants "none"; DEC-129 shell table.
  - ADM-02: a deny override narrows a manager's `request_item.create` (and capabilities) and
    nothing else; 'allow' overrides grant nothing; an exhaustive sweep of every (action, role)
    cell shows no override value widens; `set_policy_override` refuses widening, read, self-lockout
    and platform-role templates; only a firm administrator writes them.
- `backend/tests/integration/test_f03_personas_db.py` (Postgres; 12 cases): Lena's real wall row
  through `authorise`, `allowed_actions` and `visible_scope` for engagement, work_item, client and
  client_entity; `memberships.offshore` decides `tin.reveal`; `set_policy_override` narrows a
  manager, refuses an 'allow' template with nothing stored, and the table's CHECK refuses 'allow';
  Meera's grant written through `grant_client_access` (event names the granting partner, INV-5),
  portal list shows her return only; K-1-only and third-party shells; Copperleaf (tax only) reads
  `is_attest_client` False and an active audit client True.

## Progress log
- 2026-10-22: tests written and passing (67). No product defect found.
- 2026-10-22: two harness pitfalls, worth a lint rule or a helper:
  1. `visible_scope` must get a column bound to the listed table. An unbound
     `sqlalchemy.column("id")` renders bare, so the wall subquery
     (`... WHERE engagements_1.id = id`) correlates on itself and fails with "more than one row
     returned by a subquery". `tests/integration/test_visible_scope_kinds.py` (F-03-T27) does this
     and 5 of its 9 cases fail locally on main (engagement and client_entity kinds, and the
     firm-admin cases). Repository code passes bound columns, so the product is unaffected; the
     fix is in that test's `_listed`. Left for its owner and raised in the report.
  2. Engagements inserted by the superuser seeder (no tenant GUC) don't fire the
     `is_attest_client` derivation usefully: the SECURITY DEFINER trigger runs as the owner, which
     is held to RLS. Move the status under `uow(tenant)` as the app does.
