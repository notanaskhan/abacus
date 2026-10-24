---
id: TASK-1204
title: Portal PBC read model — GET /v1/portal/binders, binders/{id} and request-items/{id} (R-01-T07)
spec: SPEC-323
acceptance_criteria: [AC-3, AC-4]
risk_zone: amber
status: done
epic: R-01
plan_key: R-01-T07
branch: s8a-portal-pbc
created: 2026-10-25
updated: 2026-10-25
---

## Objective
"Claire Feld's binder returns 21 requests with 2 open matching TAX-03 Intake 2, Dana Kowalski sees
only Dana's own requests, and no field carries a firm status code or amount." Screens POR-03 and
POR-04; contract C5 section `portal-pbc` (stub R-01-T01, TASK-1042; DEC-240).

## Plan (amber zone)
- **Composition (portal owns no business truth):** `portal/documents.py` (new) builds
  `PortalBinderListOut`, `PortalBinderOut` and `PortalRequestOut` from
  - `requests.api`: `requests/portal_documents.py` (new) — the client-visible binders and their
    requests through `visible_items(request_item.read)`, with drafts, deleted, internal-only and
    **delegated** requests (open `request_delegations`) left out (INV-4); categories, live
    fulfilments (withdrawn left out, DEC-298), upload intents, the ignorer, shared comment counts,
    client guidance (SPEC-035 swap), the prior-year link (roll-forward: the prior binder's request
    of the same title), the open delegations' contacts, and whether the firm acted since a
    mark-done;
  - `evidence.api`: `evidence/portal_files.py` (new) — per live version: file name, size, source,
    method, uploader, storage mode, ever accepted, the effective send-back (reason code, note,
    who, when) and the latest client-audience pre-check codes; withdrawn versions never returned;
  - `engagements.api`: `get_ref`, `client_contact_organisations` (new, for the other-parties note);
  - `identity.api`: `authorise` (`portal_documents.read`, `scope_only`, on the binder's work
    item), `allowed_actions` per row (`evidence.upload`, `request_item.ignore`,
    `comment.create`, `evidence.withdraw`, `binder.mark_done`), `portal_scopes`, `FULL_ROLES`,
    `engagement_role_of`, `names_of`.
- **Routes:** the three stub routes in `portal/pbc_contract.py` go live behind
  `portal.documents_v2`; room, suggest and the drop poll stay stubs (T13, T09).
- **Rules (DEC-333):** filters, groups and bands, client words, receipt kinds, return-reason
  mapping, closed binders read-only, the other-parties note for client admins only.
- **No migration, no matrix or flag edit** (the stub registered them).
- **Tests:** `tests/integration/test_portal_documents.py` (AC: Claire's binder counts and words,
  Dana's own requests, Harborline's third-party grant sees nothing, forged and draft ids 404,
  closed binder read-only, withdrawn files hidden, contributor scope, firm-only C5 v1.1 fields never
  present, the route guard records `portal_documents.read`); unit tests for the pure rules
  (`tests/unit/portal/test_documents_rules.py`); the C5 stub test treats the three routes as live.
- **Rollback:** revert the commit; the flag stays off by default.

## Progress log
- 2026-10-25: plan written.
- 2026-10-25: built. `portal/documents.py` (read model), `portal/documents_routes.py` (the three
  routes, moved out of the stub module so the read model can import its models without a cycle;
  operation ids unchanged), `requests/portal_documents.py` + repository reads, `evidence/
  portal_files.py` + `ever_accepted`/`client_problem_codes`, `engagements.api.
  client_contact_organisations`. LIST_EXEMPT gains the four id-keyed lookups. The C5 stub test
  marks the live routes (`IMPLEMENTED`). Tests: `tests/integration/test_portal_documents.py`
  (11), `tests/unit/portal/test_documents_rules.py` (19). Rules recorded as DEC-333.
  Deferred to the Brightwater Hale slice (R-01-T11): the literal 21/19/2 figures, the 37 sorted
  and the Northwind/Dana band layout against the seed; the read model foots the same way on
  the smaller seeded binder here. Upload intents are counted per request (`uploading_count`);
  the binder-level `upload_intents[]` the screen contract mentions is not in the C5 model, so it
  is not served (no shape change).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-333 | Filters, groups, receipts, return reasons and other read rules the plan leaves open | No |
