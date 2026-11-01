---
id: TASK-2503
title: A-03-T02 sampling API contract stub and screen contracts (AUD-11, AUD-31, SHL-14 c)
spec: SPEC-580
acceptance_criteria: [AC-11, AC-12]
risk_zone: amber
status: done
epic: A-03
plan_key: A-03-T02
branch: s20-a03-t02
created: 2026-10-30
updated: 2026-10-30
---

## Objective
The sampling API as a contract stub (every A-03 §4.3 sampling route, classified models, the
flag, Brightwater Hale fixtures, the generated client), its two status families and the screen
contracts AUD-11, AUD-31 and the SHL-14 c addendum.

## Plan (amber)
- `sampling/contract.py`: models (populations, ties, sources, parameters, strata, versions,
  items, draw progress, fan-out preview and result; inputs with no seed field); three routers
  (`/v1/work-items/{wid}`, `/v1/populations`, `/v1/sample-sets`); gates `work_item_gate`
  (client 404 → engagement authorise → flag) and `target_gate` (client 404 → non-person refused
  on a write → the read at firm level → flag), DEC-1553; reads of fixture ids answer the fixture,
  everything else 501. `sampling.api.ROUTERS` mounts them.
- `sampling/contract_fixtures.py`: Northwind Participants Version 2 (25 named participants in
  draw order, census v2 412 with two ties) and Version 1 (census v1 409, off 182,300.00);
  Granite Peak disbursements (1,912; strata 24/1,102/786; 40 items 3,698,700; seed 0x7C31B4).
  Values only from the AUD-11 handoff; undesigned values are null (stratum amounts, GL account
  codes, the GL deviation definition).
- Status vocabulary: `sample_set_version`, `completeness_tie_result`; `make regenerate`
  (`_statuses.py`, `status.gen.ts`, the route-introspection suite, the client).
- Docs: `docs/contracts/sampling.md` (+ register row), `docs/screens/AUD-11.md`,
  `docs/screens/AUD-31.md`, the SHL-14 c addendum.
- Rollback: revert; the routes are flag-gated and write nothing.

## Acceptance
| Check | Test |
|---|---|
| Every route, its one action, 404 and 501 documented; the family is exactly these | `tests/contracts/sampling/test_sampling_stub.py::test_ac11_*` |
| Idempotency keys; no seed input; fields classified | same file |
| Gate order and the non-person refusal; fixtures and 501 | same file |
| Status families generated | `test_ac12_the_status_families_are_generated` |

## Progress log
- 2026-10-30: built (tests first, run at the end review). DEC-1553.
