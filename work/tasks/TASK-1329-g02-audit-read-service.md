---
id: TASK-1329
title: audit_trail read service and routes (G-02-T08)
spec: SPEC-349
acceptance_criteria: [AC-1, AC-2, AC-3, AC-4, AC-5, AC-6, AC-7, AC-9, AC-10]
risk_zone: red
status: in-review
epic: G-02
plan_key: G-02-T08
branch: s10b-audit-read-service
created: 2026-10-26
updated: 2026-10-26
---

## Objective
Turn `GET /v1/audit-events` and `GET /v1/audit-events/{seq}` live (export stays 501 until
G-02-T17): `audit_trail.api.list_events`, `get_event`, `events_for_work_item`; the activity
catalogue v1 with registry collection and generic fallback; a static check that every audited
action literal has an entry or is on the reviewed fallback list.

## Plan
- **Kernel read surface** (`kernel/uow/explorer.py`, new file beside the chain): the Core
  `audit_events` table for composed reads (as `audit_activity()` does) and the leaf version that
  covers a `seq`, so the module never names the kernel's tables in SQL (OWN-001).
- **Visibility** (`audit_trail/explorer.py`), bound by the S9 security review:
  - the event's engagement is `engagement_id`, else the target when it is an engagement; rows
    with an engagement pass `visible(ctx, "audit_event.read", engagement)` (roles, in-scope and
    walls on the engagement's client, so walls key on a client derived from `engagement_id`);
  - rows with no engagement are firm-level: only firm-level readers (`firm_admin`,
    `security_admin`, platform support, each authorised at the firm, and the QM owner
    `quality_partner`) see them; engagement roles never do; a reader walled from any client
    sees only firm-level kinds among them (unplaced history fails closed);
  - a stored `client_id` the reader is walled from hides the row whatever else holds;
  - all of it in SQL, so `total` and `counts` never include an omitted row (DEC-43).
- **Projection:** actor grammar (person, via_agent with `on_behalf_of`, policy, system, support);
  `ok` only for a person or policy actor; `detail_facts` from the refs, ids, counts and codes
  only (fingerprints dropped); request context only for `REQUEST_CONTEXT_READERS` (DEC-420);
  `content_hash` the event's leaf at the covering checkpoint's version.
- **Paging:** keyset on `seq` (descending; ascending after `since_seq`), sealed P-36 cursor,
  capped totals and counts per actor kind.
- **Catalogue** (`activity_catalogue.py`, `activity_reviewed.py`): entries, module registration
  (`register_activity_kinds`) and a suffix fallback; `tests/unit/audit_trail/test_activity_catalogue.py`
  walks `record("…")` literals.
- Contract doc, contract test (list and detail now live), AC suite 1 `STUBBED` narrowed.

## Tests
`tests/integration/test_g02t08_audit_read_service.py` (manager gets `ip` null, firm-level events
invisible to engagement roles, walls on derived client, work-item read), suite 1 live,
`tests/unit/audit_trail/test_activity_catalogue.py`, `tests/contracts/audit_log/`.

## Rollback
Flag `audit_log.explorer` off (404). No migration in this task.

## Progress log
- 2026-10-26: built with T09, T10 (one targeted test pass at the end). List and detail live;
  firm-level events and request context through two new matrix rows
  (`audit_event.read_firm_level`, `audit_event.read_request_context`) because AUTHZ-002 keeps
  firm roles out of module code (DEC-434). AC suite 1: `STUBBED` narrowed to the export family;
  AC-4 reworked to the binding (Hannah reads through Copperleaf only). The office filter's
  actor-office fallback (DEC-415 Q9) waits for an identity reader. Found ED-112 (`sign_off`
  target unplaced on main; `test_targets` fails there too). Targeted pass: 8,131 passed, 1 failed
  (ED-112). Mistake made twice: reading `ctx.firm_role` in module code (AUTHZ-002) and naming a
  class after a banned glossary word (`Activity`, `project`); both caught by `banned_patterns`.
- 2026-10-26: security review fixes. M1: firm-level events whose references name a walled
  client (or an unplaceable client-side id) are hidden from a walled reader in list, detail,
  counts and search. L3: search is a predicate in the list query. L5: role rows probed via
  `allowed_actions`. L7: an IPv6 zone in `ip` answers 422. **Known gap:** writers fill neither
  `audit_events.client_id` nor `office_id`, so the Office filter matches nothing yet (DEC-436).
