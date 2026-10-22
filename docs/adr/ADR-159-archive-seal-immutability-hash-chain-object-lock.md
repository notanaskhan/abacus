---
id: ADR-159
title: Archive seal, database immutability, the audit hash chain and Object Lock modes
status: proposed
date: 2026-10-22
deciders: ayushkbhatia, notanaskhan
risk_zone: red
---

> **Instructions for coding agents**
> - Accepted ADRs are binding. Code that contradicts one must not be written.
> - If a task seems to require breaking an ADR, propose a new ADR that supersedes it. Never work around it silently.
> - Never edit an accepted ADR. Propose a new one that supersedes it.

## Context
ADR-007 makes the audit trail append-only, and ADR-016 puts evidence under S3 Object Lock, but neither says how a reviewer proves the log is unaltered, which records need COMPLIANCE rather than GOVERNANCE mode (conflict C-09), or how a locked work item stays immutable while the post-issuance trail keeps growing (C-13). Accrued must pass the M7 real-data gate (Q-02) with these answered. Plan decision DEC-71 settles them; this ADR is P-43 in the plan's ADR backlog. F-04 R-12 adds that business time (`audit_events.effective_at`, ADR-143) must be covered beside system time.

## Decision
- **Per-tenant hash-chain checkpoints.** Every five minutes (after a 120-second settle window) each tenant's new `audit_events` are sealed into an `audit_checkpoints` row:
  - **leaf** = SHA-256 of the row's canonical form, **leaf version 1**: `tenant_id, seq, occurred_at, effective_at, actor_kind, actor_id, on_behalf_of_user_id, action, target_type, target_id, before_ref, after_ref, trace_id`, serialised as sorted-key JSON with RFC 3339 UTC timestamps. A new field means leaf version 2; old checkpoints keep their version.
  - **merkle_root** over the range's leaves, in `seq` order.
  - **chain_hash** = SHA-256(previous chain hash ‖ root ‖ seq range ‖ count).
- **Verification.** A nightly verifier recomputes every checkpoint, reports the first broken one, flags a late commit (a row inside a closed range) and raises a SEV1 (audit-chain mismatch). App transactions are capped under 60 seconds, so a late row is a fault or tampering. The restore drill verifies the restored copy.
- **Daily anchors.** Each day's last chain hash is written to the `records` bucket's COMPLIANCE prefix with retain-until of at least seven years, so a database restore cannot rewrite history undetected.
- **Object Lock modes per record class.** Evidence objects: GOVERNANCE, with `s3:BypassGovernanceRetention` denied to every app role (SCP). Seal manifests, signature and consent packages and chain anchors: COMPLIANCE. Retain-until comes from the record class's retention policy (P-14) and only ever extends.
- **Database immutability.** A Postgres trigger makes a locked work item and its children immutable, except `archive_additions`, `post_issuance_events` and `audit_events` (append-only anyway). A scoped `archived_write` exception covers exactly those, for A-07.
- **Run records.** Decision-relevant agent run records are persisted with their hash and cross-referenced to P-47.

## Options considered
### Option A: checkpointed Merkle chain, anchored daily in COMPLIANCE storage — chosen
- Pros: tamper evidence without per-row cost; cheap verification; anchors survive a database restore.
- Cons: a background job and a verifier to run; a five-minute window before an event is sealed.

### Option B: per-row hash chain (each row hashes the previous)
- Pros: immediate sealing.
- Cons: serialises every insert in a tenant; a hot row; insert order must equal commit order.
- Why rejected: contention at busy-season load, and commit order isn't insert order.

### Option C: rely on database permissions only (ADR-007 as written)
- Pros: nothing to build.
- Cons: a superuser or restore can alter history with no trace.
- Why rejected: fails the M7 gate's "prove the log is unaltered".

## Consequences
**Positive**
- ADM-07 can show "immutable" with a checkpoint to prove it; exports carry the latest root.
- Records that law or contracts fix (seals, signatures, consents) can't be shortened by anyone.

**Negative / costs accepted**
- COMPLIANCE mode can't be undone; a wrong retain-until on a COMPLIANCE object stands until it expires.
- A canonicalisation change is a new leaf version, never an edit.

**Follow-up work created**
- Code: `audit_checkpoints`, the sealer schedule and nightly verifier (Q-02 §3.6, T21); COMPLIANCE writes and per-class retain-until (Q-02 §3.7); the immutability trigger and `archived_write` (A-07); run-record persistence (P-47).
- Ops: the bypass-deny SCP (Q-01-T29); the audit-chain mismatch runbook.

## Enforcement
- [ ] Test: altering or deleting an audit row in a test database is reported at the first broken checkpoint (Q-02 AC-27).
- [ ] Test: a late commit inside a closed range is flagged (AC-28).
- [ ] Test: the app role's governance-bypass attempt is denied on staging (AC-33).
- [ ] Test: leaf version 1 covers `occurred_at` and `effective_at`.
- [ ] Advisory only — none.

## Guidance for agents
Never update or delete `audit_events`; never write a COMPLIANCE object outside the records writer; compute retain-until from the policy, never a constant. A new audit column changes the leaf only through a new leaf version.

## Related
- Plan: P-43 (section 9.4.2); DEC-71; Q-02 §3.6–3.7, conflicts C-09 and C-13; F-04 R-12.
- ADRs: ADR-004, ADR-007, ADR-016 (modes amended here), ADR-143 (`effective_at`); P-14 (retention), P-47 (run records).
