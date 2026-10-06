---
id: ADR-103
title: Table ownership by registry, not name prefix
status: accepted
date: 2026-10-06
deciders: Founder
risk_zone: amber
---

> **Instructions for coding agents**
> - Accepted ADRs are binding. Code that contradicts one must not be written.
> - If a task seems to require breaking this ADR, **stop** and raise it.
> - Never edit an accepted ADR. Propose a new one that supersedes it.

## Context
ADR-008 says each module owns tables prefixed with its name. SPEC-000 §7, the glossary's code names and migration 0004 use plain names (`engagements`, `memberships`, `request_items`). Prefixes would give names like `engagements_engagements` and drift from the glossary, which is binding vocabulary.

## Decision
Tables use the glossary's plural code names, with no module prefix. Ownership is declared in `TABLE_OWNERS` in `abacus_tools.quality.schema_check`, which maps every table to the module or kernel package that owns it. `schema_check` fails on any table missing from the map, or listed but absent. This supersedes ADR-008's sentence on table prefixes; the rest of ADR-008 stands.

## Options considered
### Registry — chosen
- Pros: Names match the glossary. Ownership is explicit and machine-checked.
- Cons: One more place to update when adding a table.
### Prefixes
- Pros: Ownership is visible in the name.
- Cons: Awkward names; diverges from the glossary; means renaming migration 0004's tables.
- Rejected.

## Consequences
**Positive**
- Every table has exactly one declared owner, reviewed with the protected `schema_check`.

**Negative / costs accepted**
- Reviewers check `TABLE_OWNERS` rather than reading ownership off the name.

## Enforcement
- `schema_check`: every table is in `TABLE_OWNERS`, and every entry exists.
- Reviewer checklist: queries touch only the module's own tables (ADR-008).

## Guidance for agents
Add new tables to `TABLE_OWNERS` in the same change as the migration.

## Revisit when
Modules are split into separate services.

## Related
- ADR-008
- ADR-101
