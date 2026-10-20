---
id: ADR-150
title: Integrations module and the declared write-capability framework
status: proposed
date: 2026-10-20
deciders: ayushkbhatia
risk_zone: red
---

> **Instructions for coding agents**
> - Accepted ADRs are binding. Code that contradicts one must not be written.
> - If a task seems to require breaking an ADR, propose a new ADR that supersedes it. Never work around it silently.
> - Never edit an accepted ADR. Propose a new one that supersedes it.

## Context
**Accept by 2026-11-27.** ADR-040 says connector clients implement read operations only and no write methods exist. The product now needs writes (GL posting, tax-engine export, mailbox, webhooks, e-signature), and firm, personal and client systems are not distinguished. Plan decision DEC-46 settles the shape; this ADR is P-17. Without it, either every write class needs its own ADR (about eight) or writes are built outside review.

## Decision
- **New red `integrations` module.** A data-driven catalogue with three ownership modes (firm, personal, client-authorised), health, and `integration_interest`. Only connectors that really exist show as "Available".
- **`write-capabilities.yaml` (protected)** lists every write; a capability not in it cannot run.
- **A write runs only** from a human-approved action, through a declared adapter, with an idempotency key, a dry run, write-once request/response evidence and a client-visible log.
- **`connections` stays read-only**; CONN-001 is intact.
- **Adapter ADRs only** for W1 GL posting (P-16), W2 tax engine (P-18), W6 mailbox (P-60) and W8 webhooks (inside P-21).

## Options considered
### Option A: a framework plus a few adapter ADRs — chosen
- Pros: one gate for every write; ADRs only where a new trust boundary appears.
- Cons: a shared kernel and registry to build first.

### Option B: one ADR per write class (about eight)
- Pros: each write reviewed alone.
- Cons: many ADRs repeating one gate.
- Why rejected: only W1, W2, W6 and W8 cross a new trust boundary.

## Consequences
**Positive**
- Reads and writes are separated; every write is declared, gated by a human and logged.

**Negative / costs accepted**
- Nothing writes until the registry and gate exist.

**Follow-up work created**
- Code: `modules/integrations`, `execute_write()` and the write-interception test (EP-14, EP-17, EP-18; registry skeleton A-02-T15, S11).
- Specs: WB-10/11, ADM-08, TAX-09, CLS-07/11, INB-01/03, POR-16, ATT-09 follow.
- Glossary: ownership mode, write capability (`docs/product/glossary.md`).
- Matrix: `write_capability.execute` human-only; `integrations` grants (C-02-T02).
- Registry: `docs/architecture/write-capabilities.yaml` plus a runbook entry for write incidents (RB-30).

## Enforcement
- [ ] Lint rule: no write-shaped methods on `Connector`.
- [x] Architecture / dependency rule in CI: writers are callable only through `execute_write()`.
- [x] Test: the write-interception harness fails on any undeclared outbound non-GET request.
- [x] Hook or protected path: `write-capabilities.yaml`.
- [ ] Reviewer agent checklist item: new write has a registry row.
- [ ] Advisory only — reason: n/a

## Guidance for agents
Do not add a write method to a connector. Declare it in the registry and call it through the gate. The agent principal never holds `write_capability.execute`.

**Do**
```
execute_write(ctx, capability="ledger.post_journal_entries", approval_ref=ref)
```

**Don't**
```
class QboConnector:
    def post_entry(self, ...): ...   # write on a read connector
```

## Revisit when
A write class crosses a new trust boundary not named above.

## Related
- ADRs: supersedes in part ADR-040's clause "connector clients implement read operations only; no write methods exist"; keeps the egress allowlist, access log and honest consent copy of ADR-040. Sibling of ADR-037 (one connector contract).
- Plan: P-17; DEC-46; ch. 06 D-OPS-19 and §7.4 (the plan's text calls the framework P-39); Q-19.
- Specs: SPEC-025 untouched.
