---
name: compliance-kernel
description: How to use the compliance kernel when a change touches client data — classification tags, audit and actor attribution, the human-only guard, access events, retention and legal holds, incidents, firm export and fresh MFA. Use for any red or amber backend work that reads, writes, exports or deletes client data.
---

# Compliance kernel

**Contract:** `docs/contracts/compliance-kernel.md` (v1.3). **Spec:** `docs/specs/SPEC-341-compliance-kernel-real-data-readiness.md`. **Runbooks:** RB-14 (legal holds), RB-27 (Accrued incident propagation), RB-29 (integrity and audit chain), RB-39 (agent stages), RB-40 (provider terms and Bedrock parity).

## Every model field is classified (ADR-031)
`Annotated[T, classified("public" | "internal" | "confidential" | "restricted")]` on every Pydantic and dataclass field that crosses a boundary. Restricted values (TINs, account numbers) are never logged and leave only through `kernel.classification.mask` or a logged reveal (P-03's PII reveal). Domain events refuse Restricted fields: expose a read API instead.

## Every state change is audited, with the right actor (ADR-007, ADR-018)
Write inside `async with uow(ctx.tenant) as tx:` and call `tx.record(action, target=Target(...), after=Ref(...), scope=Scope(...))`. No `record`, no commit (`MissingAuditEvent`): catch it only to mean "nothing changed". `after` holds identifiers, codes and counts, never names, amounts or free text. A new action joins the activity catalogue or `audit_trail/activity_reviewed.py`.

## Humans decide (ADR-005, INV-1)
A decision action is in `kernel/_human_only_actions.py` (generated from the register): an agent, the system or support asking is refused and audited (`decision.refused_non_human`) in its own unit of work so the refusal is kept. Never add an agent or system cell to a decision action in the matrix.

## Reads of client content leave access events
List and detail reads of content register an access kind (`kernel.access.register_access_kind`) and record through `record_reads`; walls answer 404 with no count (DEC-43).

## Retention and holds fail closed
Before deleting anything, ask `holds_covering`; with no hold check registered, retention and erase refuse. Evidence and ledger snapshots are never updated or deleted (create new versions).

## Fresh MFA and onshore
Exports, downloads, publishes and reveals carry `mfa_recent: required` (and `not_offshore` where client content leaves) in the module's matrix file; the service still checks a recorded factor time before it writes.

## Time and incidents
Time from `abacus.kernel.clock` only (CLOCK-001). Incident clocks are computed by code (`ftc_notify_by` = discovery + 30 days; Accrued's DPA notice 72 hours from confirmation).

## Before you open the PR
- Matrix rows for new actions, with agent and system `deny`; `make regenerate`.
- Audit action in the catalogue or reviewed list; new table in the module registry with forced RLS (`tenant_table`) and insert or update column grants.
- A security review of the red diff (inline when there are no subagents).
