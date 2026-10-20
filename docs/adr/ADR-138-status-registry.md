---
id: ADR-138
title: One status vocabulary file is the contract; enums, OpenAPI and UI tables are generated from it
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
Status words appear on every pill, tile, filter and enum. The design handoff's `lib/status.js` was drafted without blueprint section 3.3.1 and conflicts with it on 17 objects; the repo has its own hand-written enums. Without one source, backend enums, OpenAPI enums and UI labels drift apart. Plan decision DEC-08 settles this; this ADR is P-34 in the plan's ADR backlog.

## Decision
The status vocabulary is authored once in `docs/product/status-vocabulary.yaml`, from blueprint 3.3.1, addendum 3.2 and gap 6.5. Each object lists its codes, labels (with optional context variants, for example "Draft" on 1040/1041 returns and "Working" on entity returns), variant, terminal flag and client label. Backend `StrEnum`s, migration CHECK strings, OpenAPI enum names and `packages/ui/src/status.ts` are generated from that file and never edited by hand. Only the visual tables from `lib/status.js` are kept. API responses carry status codes and context, not display labels.

## Options considered
### Option A: blueprint 3.3.1 + addendum 3.2 + gap 6.5, authored once in YAML, then generated — chosen
- Pros: one contract; drift is mechanically detectable; context labels fit.
- Cons: a codegen tool and a drift check to build and maintain.

### Option B: the handoff's `lib/status.js`
- Pros: already exists and matches the screens.
- Cons: a mock drafted without 3.3.1; conflicts on 17 objects.
- Why rejected: it is not the contract.

### Option C: the repo's current enums
- Pros: already in the code.
- Cons: hand-written, no context labels, not aligned to the blueprint.
- Why rejected: same drift problem, in the other direction.

## Consequences
**Positive**
- Every pill, tile, filter and enum reads from one file.

**Negative / costs accepted**
- Editing the YAML without regenerating fails the fast check.
- Status words the file lacks must be added to it before their screens are built.

**Follow-up work created**
- Code: `abacus_tools/codegen/status_vocabulary.py` and the drift check in `make check-fast` (epic F-03, S0-S4; task F-03-T09). Tolerant status reader in legacy screens (F-03-T11).
- Specs: epic specs cite `status-vocabulary.yaml` by code, never a literal label (F-03, S0-S4; F-05, S0-S10).
- Glossary: none.
- Matrix: none.
- Registry: `docs/product/status-vocabulary.yaml` authored and listed in `docs/architecture/protected-paths.md` (F-03-T04, S0-S4); `packages/ui/src/status.ts` generated (F-05, S0-S10).

## Enforcement
- [x] Test: drift check in `make check-fast` fails if the YAML and generated files differ.
- [x] Test: conformance tests for 3.3.1 coverage, the `status.js` mapping, and OpenAPI enums contained in the YAML (F-03-T10).
- [x] Hook or protected path: the YAML is a protected path.
- [ ] Advisory only: none.

## Guidance for agents
Add or change a status by editing the YAML and running the generator. Return `status: {code, context?}` from the API; the UI maps it to label and variant from the generated table. Server-built labels exist only in deterministic documents and emails.

**Do**
```python
from abacus.kernel._statuses import RequestItemStatus   # generated
```

**Don't**
```ts
const label = status === "open" ? "Requested" : "Done";  // hand-written label table
```

## Revisit when
A new status object type cannot be expressed in the file's schema, or labels must vary by a dimension beyond context.

## Related
- Plan: P-34 (`docs/plan/09-decisions-adrs.md` section 9.4.2); DEC-08; Q-02, D-DS-3, FE-06, G-D02.
- Supersedes or amends: none. The plan row lists no existing ADR; ADR-013 (Pydantic as schema source) is unchanged.
- Docs: `docs/product/status-vocabulary.yaml`.
