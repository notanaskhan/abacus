---
id: ADR-190
title: API status fields carry the bare code; the label context is the screen's, and a server-known discriminator travels as its own field
status: accepted         # amends ADR-138's "Return `status: {code, context?}`" sentence
date: 2026-10-26
deciders: ayushkbhatia   # accepted by Ayush on 2026-10-26 (DEC-413)
risk_zone: amber
---

> **Instructions for coding agents**
> - Accepted ADRs are binding. Code that contradicts one must not be written.
> - If a task seems to require breaking an ADR, propose a new ADR that supersedes it. Never work around it silently.
> - Never edit an accepted ADR. Propose a new one that supersedes it.

## Context
ADR-138 (accepted) says "Return `status: {code, context?}` from the API", and F-03-T09's
acceptance repeats it ("every API status field serialises as {code, context}"). Nothing on `main`
does this: every response model since S1 returns the status as a bare code (`status: "in_review"`),
the generated OpenAPI enums and `@abacus/api-client` types are built on that shape, and the frozen
contracts (C1 work items, C5 requests and binders, and the rest in `docs/contracts/README.md`)
record it. The 2026-10-26 reconcile found the clause unbuilt across S0-S9.

The vocabulary's contexts (`docs/product/status-vocabulary.yaml`, `context_labels` and
`context_variants`) are, with one exception, **rendering surfaces**: `subbar`, `tile`, `pill`,
`home_and_tax_tiles`, `with_lock_icon`, `sub_line_when_run_active`. The screen knows where it draws
a status; the server does not. The exception is the tax return's `preparing` label, which reads
"Draft" for 1040/1041 and "Working" for entity returns: the discriminator is the form family,
which the server knows and the return's own payload already carries (`form`).

Wrapping every status in an object now would break every frozen contract and the generated
client for no reader that needs it.

## Decision
1. API status fields are the bare code from the vocabulary (`status: "<code>"`), typed by the
   generated enum. No `{code, context}` wrapper.
2. The context that selects a label or variant is chosen by the SPA from where it renders the
   status (`statusLabel(object, code, context)` over the generated table).
3. Where a label depends on a fact only the server knows, that fact is its own field on the same
   payload (for example the return's `form`), never a server-built label.
4. ADR-138's other rules are unchanged: one YAML, generated enums, CHECK strings, OpenAPI enums and
   UI tables; the drift check in `make check-fast`; no display labels from the API.

## Options considered
### Option A: bare codes, screen-chosen context — chosen
- Pros: matches every frozen contract and the generated client; no migration of readers; the
  context stays with the code that knows it (the screen).
- Cons: amends an accepted ADR's sentence.

### Option B: wrap every status as `{code, context?}`
- Pros: the letter of ADR-138 and F-03-T09.
- Cons: breaks every frozen contract (C1, C5, ...) and every generated type; the server would
  have to guess rendering surfaces it cannot see; `context` would be null nearly everywhere.
- Why rejected: cost without a reader.

### Option C: a sibling `status_context` on every payload with a status
- Pros: additive.
- Cons: the same guessing problem; one more field to keep in sync.
- Why rejected: the one real discriminator (form family) already exists as data.

## Consequences
**Positive**
- F-03-T09's remaining clause closes without a contract break once this is accepted.

**Negative / costs accepted**
- A future server-known discriminator needs its own field and a vocabulary note naming it.

**Follow-up work created**
- Done on acceptance: ADR-138 marked "amended by ADR-190" in `docs/adr/README.md`. F-03-T10's
  conformance tests check that no response model wraps a status (a status field is a vocabulary
  enum or a nullable one).

## Enforcement
- [x] Test: the existing OpenAPI conformance (`abacus_tools.codegen.status_vocabulary` drift check
  and F-03-T10's "OpenAPI status enums contained in the YAML") already fails on a status literal
  outside the vocabulary.
- [ ] Reviewer agent checklist item: a new status field is a generated enum, not an object.

## Guidance for agents
**Do**
```
class ReturnOut(BaseModel):
    status: ReturnStatus      # generated enum, bare code
    form: FormCode            # the discriminator the "preparing" label needs
```

**Don't**
```
class ReturnOut(BaseModel):
    status: dict[str, str]    # {"code": "preparing", "context": "subbar_1040_1041"}
```

## Revisit when
A status label must vary by a fact the payload cannot carry as its own field.

## Related
- ADRs: ADR-138
- Specs: SPEC-306 AC-2 (status codegen)
- Docs: `docs/product/status-vocabulary.yaml`, `docs/contracts/status-registry.md`, DEC-413
