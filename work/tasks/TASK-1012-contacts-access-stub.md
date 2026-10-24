---
id: TASK-1012
title: Contacts and portal-access contract stub — CLI-04 models, nine 501 routes behind contacts.v2, matrix rows, contract doc and tests (P-07-T17)
spec: SPEC-321
acceptance_criteria: [AC-7, AC-21]
risk_zone: red
status: done
epic: P-07
plan_key: P-07-T17
branch: s6-clients-engagements
created: 2026-10-24
updated: 2026-10-24
---

## Objective
"The stub merges in the S6 batch and the consumer suite runs in notanaskhan's CI." (P-07-T17.)

## Plan (red zone)
- **Code:** `organisations/contacts_contract.py` *(new)*: classified models (contacts page with header counts and delegated footer, drawer, contact in/patch/out, grants with scope kinds and delegated request ids, invitation in/out without a token, revoke, change scope, unlock) and nine routes, each one matrix action, 404 with the flag off and 501 on. Registered in `organisations.api.ROUTERS`. Error classes `invitation_expired`, `invitation_used`, `scope_outside_client` for the live task.
- **Flag:** `contacts.v2` in `docs/architecture/feature-flags/organisations.yaml` (regenerated into `_flags.py`).
- **Matrix:** `contact.read`, `contact.manage` (new, organisations); `client_access.grant`, `client_access.revoke`, `contact.unlock` reused from identity.
- **Docs:** `docs/contracts/contacts-access.md`, register row, DEC-226.
- **Tests:** `tests/contracts/contacts_access/test_contacts_access_stub.py` (13 cases); `tests/unit/api/test_app_gates.py` knows which new POSTs create (201) and which do not.
- **No migration** (P-07-T25 owns `contacts_access`). Rollback: revert the commit and regenerate.

## Progress log
- 2026-10-24: stub built; contract and gate tests pass; `make regenerate` run. Live behaviour, fixtures and the consumer suite are P-07-T25, P-07-T11 and P-07-T18.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-226 | Missing F-03 contact rows, paths beside identity's invitations, footer shape, no token | No |
