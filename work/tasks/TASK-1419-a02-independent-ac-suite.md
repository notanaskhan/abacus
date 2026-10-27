---
id: TASK-1419
title: Independent AC suite for the integrations framework and write-capability registry (A-02-T19)
spec: SPEC-333
acceptance_criteria: [AC-49, AC-50]
risk_zone: red
status: done
epic: A-02
plan_key: A-02-T19
branch: s11-integrations
created: 2026-10-27
updated: 2026-10-27
test_session: A-02-T19 (ADR-078 separate test author; did not write A-02-T12 or A-02-T15)
---

## Objective
"The suite fails on each seeded violation (undeclared host, hand-edited registry, enabled
capability without an ADR) and passes on main."

## Plan
Tests only, written from A-02 AC-12.2 and AC-13.1 to AC-13.3, SPEC-333 AC-49 and AC-50, ADR-040,
ADR-150 and C20 v1 §2, §3 and §6. No implementation, migration, registry, flag or matrix edit.
Each seeded violation lives on a temporary copy of the protected YAML or the generated module, or
on the in-memory compiled values (monkeypatched), never on a tracked file.

- `backend/tests/unit/integrations/test_a02t19_registry_independent.py`: fail-closed adapters
  (write-shaped methods, public HTTP clients, dishonest `read_methods`, bad keys, categories,
  scopes and hosts; a refusal registers nothing); catalogue honesty on both surfaces and all
  ownership modes; drift (six hand edits of `_capabilities.py`, a YAML edit without regenerating,
  a generated module that enables a write does not load and the API does not start, a stray
  `EGRESS_HOSTS` widens nothing); an enabled capability or one without its decision does not
  compile and generates nothing; every decision main names exists; registry-level write and
  attest refusal; nobody holds `write_capability.execute`; only the gate imports `writers` or
  `_capabilities`; an undeclared host stops start-up, hosts are declared per adapter, start-up
  admits exactly the declared hosts, a late registration widens nothing.
- `backend/tests/unit/connections/write_interception.py` (the harness extension) and
  `test_a02t19_write_interception.py`: every httpx request is caught at the transport; the
  harness fails on a write-shaped method, an undeclared host or plain HTTP, including from a
  client built around `kernel.egress`; allowlisted provider read POSTs pass; undeclared hosts and
  redirects never leave the process; the demo ledger's pull sends nothing.
- `backend/tests/integration/backfill/test_a02t19_integrations_independent.py`: sealed secrets
  (a blob moved onto another install or into another firm does not open; never stored in the
  clear; the tenant key; erase removes the only copy, audited); every write refused and audited
  once with a fingerprint; defence in depth (a registry seeded to permit meets the matrix, and
  with the matrix seeded away v1 still refuses); W1 refused for an attest client with the entry
  seeded enabled.

Rollback: delete the four test files.

## Progress log
- 2026-10-27: suite written and run once (targeted, `-n 2`): 103 passed, 1 failed (my own test:
  a unit of work with nothing to erase recorded no audit event; fixed in the test), 3 xfailed.
  Re-ran the failure (passed) and, because another session rewrote `kernel/egress.py` in this
  worktree during the run, the two unit files against the new client: 85 passed; 12 passed and
  3 xfailed. ruff format and check, pyright (0 errors), banned_patterns and secrets_scan clean.
- Defect ED-156 (strict xfail, three cases): `kernel.egress.EgressClient.request` sends any HTTP
  method (PUT, PATCH, DELETE) to an allowlisted host; ADR-040's enforcement says the connectors'
  HTTP client exposes only GET and explicitly allowlisted provider read POSTs. No connector uses
  it yet (A-02-T26 is the first), so nothing writes today; the interception harness catches it.
- Not covered here: `client_catalog` through the definer and the POR-16 `connector_not_available`
  route (A-02-T12's and T16's suites hold them; T29 covers POR-16 independently).
