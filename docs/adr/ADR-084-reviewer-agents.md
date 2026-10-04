---
id: ADR-084
title: Reviewer agents in CI
status: accepted
date: 2026-10-04
deciders: Founder
risk_zone: amber
---

> **Instructions for coding agents**
> - Accepted ADRs are binding. Code that contradicts one must not be written.
> - If a task seems to require breaking this ADR, **stop** and raise it.
> - Never edit an accepted ADR. Propose a new one that supersedes it.

## Context
Mechanical gates cannot catch semantic problems: wrong logic that is well-formed, misleading names, subtle authorisation gaps outside the matrix.

## Decision
Four reviewer agents — architecture, security, tests, AI — run on pull requests with checklists stored in the repository. Each receives the diff, spec, relevant ADRs and checklist, and returns structured findings with severity, file, rule and suggested fix. High-severity findings block merge. For amber and red work, the reviewing model differs from the authoring model. Reviewer approval never substitutes for passing gates.

## Options considered
### Structured reviewer agents — chosen
- Pros: Catches semantic issues
- Cons: Model cost per PR
- Chosen.

## Consequences
**Positive**
- A second line of defence beyond mechanical checks

**Negative / costs accepted**
- Review cost and occasional false positives

**Follow-up work**
- Reviewer checklists

## Enforcement
- Findings posted as structured PR comments; high severity sets a failing status
- Checklists versioned under `.claude/agents/`

## Guidance for agents
Address or explicitly dismiss every finding with a reason.

**Do**
```python
# Finding SEC-H1 resolved: added visible() filter in list_items
```

**Don't**
```python
# merging with unresolved high-severity findings
```

## Revisit when
Never expected to change.

## Related
- ADR-083
