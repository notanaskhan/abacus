---
id: ADR-137
title: The backend has 29 modules with a one-way dependency graph
status: accepted
date: 2026-10-20
deciders: ayushkbhatia
risk_zone: amber
---

> **Instructions for coding agents**
> - Accepted ADRs are binding. Code that contradicts one must not be written.
> - If a task seems to require breaking an ADR, propose a new ADR that supersedes it. Never work around it silently.
> - Never edit an accepted ADR. Propose a new one that supersedes it.

## Context
ADR-008 fixes the modular monolith at thirteen modules: identity, organisations, engagements, requests, evidence, connections, ledger, sampling, agents, audit_trail, communications, notifications, platform. The product adds review, signatures, workpapers, reporting, four service lines and more. Without a decided map, new tables land in the wrong module or in ad hoc ones, and cross-module imports grow into cycles.

## Decision
1. The backend has **29 modules**: the 13 existing ones plus 16 new: `methodology`, `review`, `collaboration`, `workpapers`, `adjustments`, `signatures`, `integrations`, `reporting`, `assurance`, `attest`, `tax`, `closes`, `notices`, `workbench`, `practice`, `portal`.
2. Zones: `review`, `adjustments`, `signatures` and `integrations` are red. `organisations` is upgraded to red because it holds sealed TINs and consents. `tax` and `assurance` have red paths (approval, export, filing; release, archive gate). Most other new modules are amber; `practice` is green or amber. `portal` is amber and owns no business truth.
3. **The dependency graph is one-way.** Allowed edges are declared per module in `MODULE_DEPENDENCIES` and enforced by import-linter. Nothing imports `portal`, `notifications`, `practice`, `workbench` or `audit_trail`. Shared engines (`review`, `collaboration`, `workpapers`, `adjustments`, `signatures`, `reporting`) never import a service line; they learn about targets through registration slots. Upward state changes travel as outbox events. Where a lower module needs a capability from a higher one, the higher one registers it.
4. **Registration slots** (ADR-106 pattern) carry cross-module extension, such as `engagements.register_work_item_kind`, `review.register_reviewable` and `evidence.register_citable`. A missing registration fails closed.
5. The rest of ADR-008 stands: one deployable, each module exposes only its `api` package, and no module touches another's tables.
6. Excluded on purpose: no tables, enums or engagement types for PCAOB, ESG, forensics, FedRAMP, AIUC-1, fund accounting, peer benchmarks, `single_audit`/`yellow_book`, billing or payments.

## Options considered
### Option A: the 29-module map — chosen
- Pros: every new table has a home; the graph is checkable.
- Cons: 16 new packages to create and keep wired.

### Option B: 13 modules and ad hoc growth
- Pros: no setup.
- Cons: ownership blurs, shared engines get tangled with service lines.
- Why rejected: DEC-13 chose the map.

## Consequences
**Positive**
- Clear ownership and review zones from the first new table.

**Negative / costs accepted**
- More registration boilerplate; some pairs of modules need an outbox event rather than a call.

**Follow-up work created**
- **Code:** empty packages for all 16 new modules, `MODULE_DEPENDENCIES`, import-linter contracts, worker `MODULES`, in the pre-registration PR (ADR-140). Epic EP-01, S1.
- **Specs:** module-to-screen mapping in each module's screen specs. Per module epic, by its needed-by date.
- **Glossary:** module names and the new record names (work item, sign-off). EP-01, S1.
- **Matrix:** one matrix file per new module (ADR-140). EP-01, S1; filled per module epic.
- **Registry:** the slots in section 2.4 of docs/plan/03-backend-architecture.md. EP-01, S1.

## Enforcement
- [ ] Architecture rule: import-linter contracts generated from `MODULE_DEPENDENCIES`; a new edge fails CI until declared.
- [ ] Test: the graph is acyclic.
- [ ] Test: every module is listed once in the sorted `MODULES` tuple (ADR-140).
- [ ] Reviewer agent checklist item: red-zone modules get a written plan in the task file first.

## Guidance for agents
Put a new table in the module that owns the concept. Reach another module through its `api` package, an outbox event, or a registration slot. Never import upward.

**Do**
```
review.register_reviewable("tax_return_section", provider)  # tax registers with review
```

**Don't**
```
from abacus.modules.tax import ...   # inside review: a shared engine importing a service line
```

## Revisit when
A module needs an edge the graph forbids twice, or a module exceeds a size the team can hold in one review.

## Related
- P-ID: P-05 in docs/plan/09-decisions-adrs.md section 9.4; DEC-13.
- Amends: ADR-008 Decision sentence "One deployable backend containing thirteen modules: ...". The list becomes 29. The remaining ADR-008 sentences stand.
- Related ADRs: ADR-101, ADR-103, ADR-106, ADR-140.
- Docs: docs/plan/03-backend-architecture.md sections 2.1-2.4.
