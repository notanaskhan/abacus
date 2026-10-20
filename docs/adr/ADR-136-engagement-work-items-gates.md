---
id: ADR-136
title: Engagements hold work items, and the server enforces the gates
status: accepted
date: 2026-10-20
deciders: ayushkbhatia
risk_zone: red
---

> **Instructions for coding agents**
> - Accepted ADRs are binding. Code that contradicts one must not be written.
> - If a task seems to require breaking an ADR, propose a new ADR that supersedes it. Never work around it silently.
> - Never edit an accepted ADR. Propose a new one that supersedes it.

## Context
In the repo an engagement is one audit job. The product also serves tax returns, monthly closes, notices and advisory projects, often several per client relationship (the seed has a client with 12 closes and another with 4 returns). Audit-shaped gates (acceptance, independence) must not block tax or non-attest portals. The UI must also never infer or set state by itself.

## Decision
1. `engagements` becomes the contract: an 8-state lifecycle (`prospect`, `accepted`, `declined`, `contracted`, `active`, `on_hold`, `delivered`, `archived`), a `service_line`, and an expanded `type` enum. `audit` is rewritten to `fs_audit` with no alias; `preparation` is added; AUP stays (DEC-07).
2. A **`work_items` supertype** sits under engagements, added without removing anything (DEC-07). Kinds: `assurance`, `tax_return`, `close`, `notice`, `advisory_project`. Subtype tables are owned by the service-line modules. `engagement_id` stays on every row, so `visible()` (ADR-102) and the foreign keys keep working; work-item-scoped rows add `work_item_id`. A tax engagement is per relationship or letter, and the entity lives on the work item.
3. **State machines are declarative transition tables** in each module's `transitions.py`: `(from, to, action, guard)`. An illegal transition raises `DomainConflict("illegal_transition")`. Every transition writes an audit event. Clients of the API, including the UI and Board drags, never set state directly.
4. **Gates G1-G9 are guard predicates** registered through `engagements.register_gate_provider`. An unregistered gate counts as unmet. G1-G3 stay on the engagement; G4-G9 attach to the assurance work item.
5. **A per-type gate policy** (`gate_policies`) says which gates apply: attest work G1-G9; compilation and preparation G1, G3, G5, G8, G9; tax G1 and G3 (plus consents as an attribute); non-attest CAS G1 and G3; notices G3. Firms may only make a policy stricter.

## Options considered
### Option A: additive `work_items` supertype under engagements — chosen
- Pros: one scope column keeps `visible()` unchanged; fits 1:n seed data.
- Cons: a wide migration (0056-0063 in the plan's numbering).

### Option B: one engagement per return, close or notice
- Why rejected: breaks the relationship-level contract and letter.

### Option C: a new parent contract table
- Why rejected: moves every foreign key and `visible()` call.

## Consequences
**Positive**
- Every service line shares the same engagement, request and evidence spine.

**Negative / costs accepted**
- Every non-audit screen and the Board depend on this model, so it must land first.

**Follow-up work created**
- **Code:** `work_items`, `work_item_assignments`, `assurance_work_items`, `engagement_entities`, `gate_policies`, the type rewrite, the 8-state CHECK, one binder per work item. Epic F-03 (also EP-05, EP-09, EP-10, EP-13, EP-18, EP-19), S0-S4, backfill in S1, as single migrations under ADR-135.
- **Specs:** screen specs ENG-01...03, AUD-02, TAX-02, CLS-02, NOT-02. EP-05 onward, per sprint.
- **Glossary:** add Work item and its kinds; resolve the "project" and "audit" bans (gap G-F05). F-03, S0-S4.
- **Matrix:** conditional `independence: required` on `attest_client`; request and publish rights (DEC-38). F-03, S0-S4.
- **Registry:** `register_work_item_kind` and `register_gate_provider` slots in `engagements`. F-03, S0-S4.

## Enforcement
- [ ] Test: every transition table is exercised, and an illegal transition is refused.
- [ ] Architecture rule: no module writes a status column except through its transition function.
- [ ] Test: with the gate policy, a tax engagement opens its portal on G3 without acceptance or independence.
- [ ] Test: an unregistered gate or work-item kind fails closed.
- [ ] Reviewer agent checklist item: new work-item-scoped tables carry `engagement_id` and `work_item_id`.

## Guidance for agents
Put engagement-level facts (acceptance, independence, letter, team) on `engagements`. Put the work on a work item. Never decide a gate in the UI.

**Do**
```
engagements.register_gate_provider("G3", provider)  # returns GateFact(met, blockers)
```

**Don't**
```
engagement.status = "active"  # direct write; use the transition table
```

## Revisit when
A service line needs a gate the policy cannot express, or an engagement must span firms.

## Related
- P-ID: P-04 in docs/plan/09-decisions-adrs.md section 9.4; DEC-07, DEC-39 (lifecycle, G1-G3), Q-01.
- Extends: ADR-058 (its goal, one engagement agent per engagement, is kept; agent runs gain `work_item_id`) and ADR-102 (naming and the engagement column; `visible()` semantics unchanged). No clause is superseded.
- Related ADRs: ADR-135 (migration policy), ADR-137.
- Docs: docs/plan/03-backend-architecture.md sections 3.1-3.1.4.
