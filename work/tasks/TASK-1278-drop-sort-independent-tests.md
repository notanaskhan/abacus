---
id: TASK-1278
title: ADR-078 independent AC tests for R-01-T09, the portal drop and its code-rule sort (R-01-T15)
spec: SPEC-323
acceptance_criteria: [AC-2]
risk_zone: red
status: in-review
epic: R-01
plan_key: R-01-T15
branch: s9b-portal-rooms
created: 2026-10-26
updated: 2026-10-26
---

## Objective
"The suite, written in AY's session from the contract and SPEC, passes on main without edits by
the implementing session." R-01-T09 was built in N's lane (TASK-1193, TASK-1248; DEC-323,
DEC-339).

## Plan (red zone: tests only)
- **Sources only:** R-01 §3.2 Stories 2.1 to 2.3, §4.2 to §4.4, `docs/contracts/portal-pbc.md`
  §2 and §5 to §7, DEC-58, ADR-005, ADR-090, INV-1, INV-4, INV-5. The implementing suite
  (`test_r01t09_portal_drops.py`) was read for its S3 and activity wiring only, never its cases.
- **File:** `backend/tests/integration/backfill/test_r01t15_portal_drops_independent.py`, over
  HTTP through `create_app()`, the compose S3 image and the extraction and sort activity bodies.
- **Cases (the row):** drop scope (the only match internal-only, a draft or delegated: waits; a
  contributor's drop never links to a request not assigned to them; a closed, draft, forged or
  other client's binder answers 404 and stores nothing); a rule link only on a decisive match
  (one statement for account 7302, December 2025: `rule`, request `uploaded`, no decision, audited
  `system` on behalf of the dropper; two requests alike: waits; an unreadable scan: waits; with
  `portal.drop_sort` off nothing links); the agent denied `fulfilment.confirm` and only proposing
  by task scope; the void only of an unaccepted rule link (a person's void returns the request to
  `requested` and the file to the inbox, audited `human`; a second void, an accepted link and a
  human link answer 409 `not_voidable`; a client cannot void); 48 MB and HEIC accepted, 51 MB 413
  `file_too_large`, `.zip` 415 `type_not_allowed`; a duplicate accepted, flagged
  `duplicate_of_version_id`, waiting, and the client's poll reads `waiting` with no word of it;
  every pre-change `upload_processing` history replays against today's workflow and an unpatched
  sort step is non-determinism (ADR-090).
- No product code, migration, matrix or flag change. Rollback: delete the file.

## Progress log
- 2026-10-26: written from the sources above; 28 cases pass on the branch (based on main
  bbe1cf37 plus R-01-T13, which touches none of T09's code) with no edit to T09's code.
  Observed (not a defect): a contributor may drop on the binder (202); the sort then waits,
  because the only match is not assigned to them.
