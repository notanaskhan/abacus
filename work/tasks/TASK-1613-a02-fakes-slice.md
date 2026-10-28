---
id: TASK-1613
title: Fake ledgers and feeds, the connections slice, scenario trial balances (A-02-T27)
spec: SPEC-333
acceptance_criteria: [AC-49]
risk_zone: amber
status: in-review
epic: A-02
plan_key: A-02-T27
branch: s13-a02-t27
created: 2026-10-27
updated: 2026-10-27
---

## Objective
Fakes for the ledger and feed connectors, Copperleaf's POR-16a connections as a scenario slice, and the Granite Peak and Northwind trial balance files.

## Plan
- `abacus_tools/fakes/ledgers.py`; `connections.is_networkless` (`fake_` prefix) used by the egress check and the health pass.
- `connections/synthetic.py` `seed_synthetic_connection` (exported by `connections.api`, with `quickbooks_online` and `Connection` for the fakes).
- Slice `scenarios/brightwater_hale/connections.py`, loader handler `connections.connection_seeded`, `SLICE_NEEDS`.
- `scenarios/brightwater_hale/ledgers.py` and three files in `files/`.
- Test `tests/unit/connections/test_a02t27_fakes_and_slice.py`. DEC-710.
- Rollback: revert; nothing reaches production (refused outside synthetic environments).

## Progress log
- 2026-10-27: built; the seed-demo POR-16a walk is left to the batch pass.
