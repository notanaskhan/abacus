---
id: TASK-1415
title: Write-capability registry skeleton, compiler, refusal gate and egress export (A-02-T15)
spec: SPEC-333
acceptance_criteria: [AC-50]
risk_zone: red
status: in-progress
epic: A-02
plan_key: A-02-T15
branch: s11-integrations
created: 2026-10-27
updated: 2026-10-27
---

## Objective
"Every execute_write call is refused with write_capability_refused and audited, a hand edit of
_capabilities.py fails the drift test, and a W1-shaped entry is refused for an attest-flagged
client at registry level."

## Plan
- `docs/architecture/write-capabilities.yaml` (policy file, protected by rule; ADR-150): version 1,
  `read_connectors: []` (the first live adapter, A-02-T26, declares QuickBooks Online's hosts),
  `writes:` W1 (C-02, ADR-161), W2 (T-01) and W7 (N-02) reserved, each `enabled: false` and
  naming the ADR that would enable it.
- Compiler `abacus_tools/codegen/write_capabilities.py` (`--check`, `--egress`): validates the
  file against `integrations.ports.WriteCapabilityRegistry` and writes
  `integrations/_capabilities.py` (READ_CONNECTORS, WRITES, EGRESS_HOSTS). Added to the
  Makefile's GENERATORS, `.claude/hooks/_protected.py` GENERATED and `protected-paths.md`.
- `integrations/capabilities.py`: the compiled registry as models; `egress_allowlist()` (Q-01's
  DNS Firewall export), `undeclared_egress()` (a registered adapter's host the registry does not
  declare), `policy_refusal(entry, attest_client)` (I-POLICY-NOT-ATTEST: W1 never for an attest
  client, whatever `enabled` says).
- `integrations/writers/__init__.py`: the `Writer` port only (no implementation).
- `integrations/writes.py`: `authorise_write` and `execute_write`: every call is refused
  `write_capability_refused` (409) with a reason code (unknown, attest client, not enabled),
  audited `write_capability.refused` on the client (fingerprint of the capability key, reason
  index) in its own unit of work; `authorise` on `write_capability.execute`, which no role holds.
- Matrix `permission-matrix/integrations.yaml`: `write_capability.execute` with no allowed role.
- Tests: `tests/unit/integrations/test_a02t15_write_capabilities.py` (drift, compile refusals,
  egress export, attest policy) and `tests/integration/test_a02t15_write_refusal.py` (refused
  and audited for a person, the agent and an attest client).
- Rollback: delete the registry, compiler and gate; nothing calls them yet.

## Progress log
- 2026-10-27: plan written.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
