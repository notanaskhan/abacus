---
id: TASK-920
title: Audit hash chain - checkpoints, Merkle root and chain hash, verifier (Q-02-T21)
spec: SPEC-319
acceptance_criteria: [AC-6]
risk_zone: red
status: done
epic: Q-02
plan_key: Q-02-T21
branch: q02-t21-audit-chain
created: 2026-10-23
updated: 2026-10-23
---

## Objective
"Altering one audit row in a test database makes the verifier report that checkpoint" (Q-02-T21; Q-02 AC-26; P-43). The spec field cites SPEC-319 because Q-02's compliance-kernel spec isn't written yet.

## Plan
- Migration `0106_audit_checkpoints`: `audit_checkpoints` and `audit_anchors`, both insert-only (immutable triggers) and under tenant RLS.
- `kernel.uow.chain`:
  - leaf v1: SHA-256 of the sorted-key canonical JSON over every `audit_events` column, `occurred_at` and `effective_at` included;
  - Merkle root, carrying an odd last leaf up a level;
  - chain hash = SHA-256(previous chain hash ‖ root ‖ seq_from ‖ seq_to ‖ count);
  - `seal_checkpoint` closes events past the settle window;
  - `verify_chain` recomputes every checkpoint and counts each mismatch on the `abacus.audit_chain.mismatch` metric.
- `audit_trail.api` re-exports `latest_checkpoint`, `verify_chain` and `Checkpoint`.
- `make audit-chain-verify TENANT=` and `python -m abacus_tools.audit_chain seal|verify`.
- Rollback: downgrade 0106.

## Decisions
- The chain lives in `kernel.uow`, beside the `audit_events` it reads (OWN-001: a module may not name the kernel's tables). The tables are owned by `kernel.uow`; `audit_trail` answers for the reads, as Q-02 §4.1 names.
- Checkpoints are written without an audit event (Q-02 §4.2), through `kernel.uow`'s own connection.

## What changed
- As planned. `tests/integration/test_audit_chain.py` (8) covers:
  - determinism, and the leaf covering both clocks;
  - "a new `audit_events` column must join the leaf" (R7);
  - chaining across checkpoints, and the settle window;
  - one altered row naming checkpoint 2, and a removed row naming checkpoint 1;
  - checkpoints being insert-only and per firm.
- The full `schema_check` (up, down, up), `test_schema_check_db` and tenant isolation pass.
- Also: renumbers the access-events task file to TASK-919. TASK-917 had been taken twice.

## Not done (infra and operations)
- Three Temporal Schedules: `AuditCheckpointJob` every 5 minutes, the nightly `AuditChainVerify`, and `AuditAnchorDaily`. Writing the anchor object to the records bucket's COMPLIANCE prefix is part of `AuditAnchorDaily`. The `audit_anchors` table is ready.
- The SEV1 alarm on the mismatch metric.
- Seven nightly staging verifications. These need the Schedules on staging.

## Progress log
- 2026-10-23: the tests above pass.
