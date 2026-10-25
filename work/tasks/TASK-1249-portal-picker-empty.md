---
id: TASK-1249
title: Portal binder picker answers 500 for a client with nothing published (ED-058)
spec: SPEC-323
acceptance_criteria: [AC-3]
risk_zone: amber
status: done
epic: R-01
plan_key: R-01-T07
branch: lo-portal-leaks
created: 2026-10-26
updated: 2026-10-26
---

## Objective
The S8 wave B acceptance agent reported `GET /v1/portal/binders` answering 500 for a client. Reproduced: a contributor with an engagement grant whose only binder is a draft.

## Plan
- `portal/documents.py` `list_binders`: when no binder was listed (so none was authorised), authorise `portal_documents.read` on the caller's grant scope (engagement or work item, else the client); an empty picker for a readable scope, 404 when none is (as with no grant).
- Test first: `tests/integration/backfill/test_p08t22_portal_home.py::test_leftover_the_binder_picker_of_a_client_with_nothing_published_is_empty`.
- Rollback: revert.

## Progress log
- 2026-10-26: reproduced (500), fixed, test passes; portal home, portal documents, F-03-T21 and client-upload backfill files pass. The second reported finding (the legacy request list showing a draft binder's requests) is not a defect: F-03 Story 3.1's independent tests require a client to read requested items there whatever the binder's state, and DEC-210's published-binder rule is the portal home's. Retiring the legacy list with the portal v2 surfaces is the place to revisit it.
