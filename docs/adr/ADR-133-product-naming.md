---
id: ADR-133
title: The product is "Accrued" in every UI string and document; abacus is the code namespace only
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
The repository, Python packages and many identifiers are named `abacus`. The product, its blueprint, its design handoff and the engineering plan are named Accrued. Without a rule, sessions mix the two in screens, emails and documents, or propose a rename. Plan decision DEC-01 settles this; this ADR is P-01 in the plan's ADR backlog.

## Decision
"Accrued" is the product name in every UI string, document, help text and firm-facing email. `abacus` stays the code namespace (packages, modules, database, infrastructure names) and is never shown to users. The client portal and client emails show the firm's name and never show "Accrued".

## Options considered
### Option A: "Accrued" in product, `abacus` in code — chosen
- Pros: no churn in about 120k lines; every user-facing surface is consistent.
- Cons: two names to keep apart; needs a glossary entry and a copy check.

### Option B: rename the code to `accrued`
- Pros: one name everywhere.
- Cons: touches every module, import, migration, protected list and infrastructure name, for no user value.

## Consequences
- New copy says Accrued; existing user-facing "Abacus" strings are fixed as their screens are touched.
- The portal is white-labelled: firm name and logo only.

## Enforcement
- Glossary entry: "Abacus: internal code namespace; never user-facing."
- Copy and voice lint (plan F-02) flags "Abacus" in UI strings and "Accrued" in portal code.

## Guidance for agents
- Write "Accrued" in UI text and docs; keep `abacus` in code identifiers.
- In portal screens and client emails, use the firm's display name.

## Revisit when
The company or product is renamed.

## Related
DEC-01 and P-01 (`docs/plan/09-decisions-adrs.md`); DEC-19; ADR-101.
