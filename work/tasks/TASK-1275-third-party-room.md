---
id: TASK-1275
title: Third-party room read model and invitations on delegation (R-01-T13)
spec: SPEC-323
acceptance_criteria: [AC-6]
risk_zone: amber
status: in-review
epic: R-01
plan_key: R-01-T13
branch: s9b-portal-rooms
created: 2026-10-26
updated: 2026-10-26
---

## Objective
"Marcus delegating the bridge letter sends Sam Ortiz one invitation in Brightwater Hale's name and
Sam's room returns exactly the 9 Keystone items." Screen POR-14; contract C5 section `portal-pbc`
(`GET /v1/portal/room`, `POST /v1/portal/room/suggest`; stub R-01-T01, DEC-240 deferred the
third-party role and `delegated_only` to this task). R-01 Stories 6.1 and 6.2.

## What exists (checked 2026-10-26 on bbe1cf37)
- Both routes answer 501 with `portal.third_party_room` on (`portal/pbc_contract.py`).
- `request_item.delegated` is an audit row only (`tx.record`), never an outbox event, so nothing
  can subscribe to it.
- A third party reaches nothing: neither the `third_party` matrix role nor a `delegated_only`
  condition exists (DEC-240; DEC-158 left `delegate` without cells). A `request_item` grant's
  scope resolves to its whole engagement, so `scope_only` alone would leak the PBC list (INV-4).
- Two delegation paths exist: P-06's `delegate_item` (contact must already sign in, else 409
  `contact_not_portal_user`; grants role `delegate`) and CLI-04's contact invitation (P-07-T25,
  DEC-300: pending `third_party` grants on request items, one 14-day invitation sent from the
  firm's database Invitation template `portal.invitation` in the firm's name, and the
  delegations recorded in the same unit of work).
- C19 is absent; `identity.api.consent_given(…, "third_party_disclosure", …)` is False for every
  client until T-01 registers it (fail closed).

## Plan (amber zone; the identity part is protected and red, recorded as DEC-387)
1. **Matrix (DEC-387).** `_roles.yaml` gains the client role `third_party`; the matrix grammar
   gains the cell `delegated_only`: allowed only on a request item whose facts name the person
   among its delegates (`ItemFacts.delegated_to`, filled by requests; absent facts deny, like
   `assigned_only`). List queries (`visible_items`) never reach through it: a third party reads
   only through the room, which authorises item by item. Cells `third_party: delegated_only` on
   `portal_documents.read`, `request_item.read`, `evidence.upload`, `evidence.withdraw`,
   `comment.read`, `comment.create` (R-01 §4.3, DEC-240). `make regenerate` (the `_matrix.py`
   and the generated security suites; codegen `security_tests.py` learns the role).
2. **Role derivation.** `identity.repository.engagement_role` answers `third_party` for a person
   with no staff row and no client grant on the engagement who holds an active, unexpired
   `request_item` grant (role `third_party` or `delegate`) on one of its requests (through the
   registered `request_item` scope resolver). `ClientRole` and `CLIENT_ROLES` gain it, so
   `scope_only` treats a third party as a client actor.
3. **Delegates on the item.** `requests.service.RequestItemRef` carries `delegated_to`: the
   users holding an active grant under one of the request's open delegations
   (`identity.api.delegation_holders`). The upload, comment and client-response routes already
   authorise with `item_ref(...).facts`, so they honour `delegated_only` with no route change.
4. **Room read model** `portal/rooms.py` (BFF over `requests.api`, `evidence.api`,
   `engagements.api`, `identity.api`), routes moved to `portal/rooms_routes.py` (operation ids
   unchanged, 501 dropped; `make generate`):
   - the caller's open delegations under their own active grants, of one engagement (the one
     delegated most recently; DEC-387), each authorised `portal_documents.read` with its item
     facts (`delegated_only`); anything else is never read, never counted;
   - rows by band (the request's category, in binder order), state `uploaded` / `in_review` /
     `due` / `returned` with its date, disc, firm-written guidance, files (receipts and
     `withdrawable` as POR-03), the return note, shared comment count, `allowed_actions`
     (`upload`, `withdraw`, `comment` only); `uploaded_count`, `total`, `complete`;
   - fail closed: a request of an engagement that holds a `tax_return` work item is left out
     without the C19 `third_party_disclosure` consent;
   - no room at all (no delegation, flag off, a full-client person): 404.
   - `room/suggest`: code-only file-name scoring (token overlap with the request title, ties and
     zero scores give no pre-selection) among the open, uploadable rows of the room; writes
     nothing.
5. **Invitations on delegation (DEC-388).** The invitation is CLI-04's contact invitation: one
   per person, from the firm's database Invitation template, carrying the `request_item` grants,
   with the delegations recorded in its unit of work. P-06's route keeps its 409 for a contact
   who cannot sign in yet (DEC-158), and a later item for a person who already signs in is a new
   grant with no second invitation (OQ-9). No subscriber on `request_item.delegated` is built
   (it would only duplicate that invitation), so the event stays an audit row. The consent gate
   is synchronous on both paths (a subscriber cannot fail closed before the grant exists):
   `delegate_item` and the contact-invitation delegation refuse a request of an engagement
   holding a `tax_return` work item without the consent, 409 `consent_required` (ADR P-12),
   nothing written.
6. **`third_party.uploaded` (INV-5).** A portal subscriber on `evidence.uploaded`: when the
   uploader holds an open delegation of the request, it emits `third_party.uploaded` (ids only);
   the notifications catalogue registers the kind `third_party_uploaded` (client activity, to
   the request's firm owner, else the engagement's leads), text resolved at read time.
7. **Docs.** `docs/contracts/portal-pbc.md` (room and suggest live; the role, cell and 409),
   C5 delegation 409 in its contract, DEC-387 and DEC-388, `portal.yaml` header, portal README.

No migration, no new flag (`portal.third_party_room` exists), no registry row.

## Tests (first)
`backend/tests/integration/test_portal_room.py` (AC names from the acceptance line and §3.6):
- `test_ac_marcus_delegating_sends_sam_one_invitation_and_the_room_holds_exactly_9`: CLI-04's
  invite of Sam with `third_party` on 9 of 24 Northwind requests writes one invitation (one
  `client_invitation.issued`), the delegations and nine `request_item.delegated` events; a later
  P-06 delegation after acceptance adds a grant, no invitation; the room returns exactly the
  delegated items, banded, "n of N".
- INV-4: every other request answers 404/403 through the room, the upload, comment and request
  routes; another client's and another firm's requests; a full-client person has no room; the
  flag off answers 404.
- states: in review after Sam's upload, returned with the note, complete, withdrawable own upload.
- consent: delegation on a tax engagement refused 409 `consent_required` on both paths; the room
  leaves such an item out.
- suggest: pre-selection by file name among delegated items only; a tie gives none.
- `third_party.uploaded` reaches the request owner and never a client.
Unit: `tests/unit/portal/test_room_rules.py` (state, disc, scoring), matrix grammar
(`delegated_only` parses, denies without facts).

## Rollback
Revert the commits; the flag stays off by default, so no third party reaches the room. The matrix
cells deny without delegate facts, so reverting identity is safe in any order.

## Progress log
- 2026-10-26: plan written (S9 wave B, portal workstream).
- 2026-10-26: built. Matrix role `third_party` and cell `delegated_only` (regenerated `_matrix.py`
  and the generated matrix suite; codegen knows the role); the role derived in `authorise` only
  (`authz._engagement_role_once` through the registered `third_party_on` lookup), never in
  `engagement_role`, after reading its other callers (team standing and ENG-05 would have taken a
  third party for staff). `RequestItemRef.delegated_to` feeds every existing upload, withdraw and
  comment route; comments treat a third party as a client (shared only; mentions the firm team
  only). Room read model and routes (`portal/rooms.py`, `rooms_routes.py`; the 501s gone, `make
  generate`), suggest, the consent gate, `third_party.uploaded`. Contract docs (portal-pbc,
  contacts-access, C5) and DEC-387, DEC-388. The C5 portal-pbc stub test moved the room and
  suggest to `IMPLEMENTED` and its flag test from "on is 501" to "off is 404" for the live gates;
  the C5 client-action test and the role-partition test now name the planned `third_party` cell.
  Tests: `tests/integration/backfill/test_r01t13_third_party_room.py` (12),
  `tests/unit/portal/test_room_rules.py` (19); impacted suites green (identity and requests unit,
  generated matrix, contracts, portal documents, invitations, contacts, uploads, scope isolation).
  Not verified: a third party's upload through the full S3 pipeline over HTTP (the test seeds the
  version and checks `authorise_upload` and the room); the Brightwater Hale seed's Sam holds
  template grants with no delegation rows (P-08-T18), so his seeded room is empty until the
  scenario slice (R-01-T11, blocked on DEC-348) records the delegations.
- 2026-10-26: self-review found that `authorise_items` (the request-list check whose rows
  `visible_items` then filters) let any client condition through, `delegated_only` included, so
  a third party passed the check of lists that read no rows through `visible_items` (who marked
  the list done, a client name). Fixed: only the conditions a list filters by pass it; a new case
  (`test_inv4_no_list_of_the_engagement_answers_to_sam`) fails without the fix.
