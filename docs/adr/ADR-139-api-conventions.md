---
id: ADR-139
title: API conventions - list envelope, allowed_actions, error catalogue, idempotency, classification, versioning
status: accepted
date: 2026-10-20
deciders: ayushkbhatia
risk_zone: amber
---

> **Instructions for coding agents**
> - Accepted ADRs are binding. Code that contradicts one must not be written.
> - If a task seems to require breaking an ADR, propose a new ADR that supersedes it.
> - Never edit an accepted ADR. Propose a new one that supersedes it.

## Context
About 158 operations were designed ad hoc. Frontend and backend work in sequence on shared contracts, and every pair needs one convention for lists, permissions, errors and retries. Plan decision DEC-12 settles this; this ADR is P-36 in the plan's ADR backlog.

## Decision
- **Shape and versioning.** REST under `/v1`. Every route declares one matrix action and a `response_model`, and every field is classified. Before the first real firm, a breaking change inside `/v1` is allowed when the same change regenerates the client. After go-live, breaking changes need `/v2` routes side by side.
- **List envelope.** Every index returns `{items, next_cursor, total, counts, facets}`. Cursors are encrypted keyset cursors.
- **`allowed_actions`.** Record projections carry server-computed `allowed_actions`; the UI reads them instead of checking roles.
- **Idempotency.** An `Idempotency-Key` header is required on every request with an external or client-visible effect.
- **Errors.** Fixed error codes from a catalogue, with an identifier-only `facts` object (identifiers, registry codes and integers; no free text).
- **Contract-first.** A 501 stub, its matrix action, its flag and `make generate` land together before the real implementation.

## Options considered
### Option A: one convention ADR (this one) — chosen
- Pros: one contract for every pair; generated clients stay consistent.
- Cons: a shared kernel to build first.

### Option B: decide per PR
- Pros: no up-front work.
- Cons: conventions diverge across 158 operations.
- Why rejected: sequential work on shared contracts needs one shape.

## Consequences
**Positive**
- Role checks and "detect flags by catching 403" leave the frontend.
- Names never sit readable in URLs or logs (encrypted cursors, identifier-only facts).

**Negative / costs accepted**
- Every endpoint pays for the envelope, projection and error catalogue.

**Follow-up work created**
- Code: `kernel/listing.py` envelope and cursors, identifier-only error facts (epic F-03, S0-S4; task F-03-T29); `kernel/idempotency` replay store (epic P-06, S3-S10; P-06-T06).
- Specs: each spec names endpoints, models, action, flag, pagination, error codes and `allowed_actions` (all epics from S1).
- Glossary: none.
- Matrix: every route declares one action in `docs/architecture/permission-matrix.yaml` (F-03, S0-S4).
- Registry: `docs/architecture/error-codes.yaml`, generated into exception classes and the UI message map (F-03, S0-S4). Consumer contract tests for the list envelope (F-05-T44, S0-S10).

## Enforcement
- [x] Test: unit test fails any `facts` field that holds free text.
- [x] Test: `make generate` drift check on `packages/api-client`.
- [x] Test: consumer contract tests for the list envelope (F-05-T44).
- [ ] Advisory only: none.

## Guidance for agents
Build indexes on `kernel/listing.py`, return `allowed_actions` in projections, send `Idempotency-Key` handling through the kernel, and raise codes from the catalogue. Start any new endpoint as a 501 stub with its matrix action and flag, then run `make generate`.

**Do**
```json
{"items": [], "next_cursor": null, "total": 0, "counts": {}, "facets": {}}
{"detail": "gate_unmet", "facts": {"gate": "G3"}}
```

**Don't**
```json
{"detail": "Gate G3 failed for client Acme Corp"}
```

## Revisit when
The first real firm goes live (the pre-launch breaking-change rule ends), or an external partner API needs different conventions.

## Related
- Plan: P-36 (`docs/plan/09-decisions-adrs.md` section 9.4.2); DEC-12; D-FE-6, D-FE-12, ch03 D-09.
- Amends ADR-013: its Enforcement line "Breaking changes require a new API version" now applies only after go-live; before the first real firm, a breaking change inside `/v1` is allowed when the same change regenerates the client. Everything else in ADR-013 stands.
- Docs: `docs/architecture/permission-matrix.yaml`, `docs/architecture/error-codes.yaml`.
