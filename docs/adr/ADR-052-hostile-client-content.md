---
id: ADR-052
title: Client content is treated as hostile
status: accepted
date: 2026-10-04
deciders: Founder
risk_zone: red
---

> **Instructions for coding agents**
> - Accepted ADRs are binding. Code that contradicts one must not be written.
> - If a task seems to require breaking this ADR, **stop** and raise it.
> - Never edit an accepted ADR. Propose a new one that supersedes it.

## Context
Uploaded documents may contain instructions aimed at manipulating models, deliberately or accidentally.

## Decision
Client content is passed in delimited blocks labelled as untrusted data. Documents are scanned for injection signals — hidden text, white-on-white text, instruction-like phrasing — and flagged on screening results. Model outputs are schema-constrained. Architectural defences (ADR-025, ADR-049) bound the impact of any successful injection.

## Options considered
### Layered defence — chosen
- Pros: Detection plus containment
- Cons: Some false positives
- Chosen.

### Prompt instructions only
- Pros: Easy
- Cons: Easily bypassed
- Rejected.

## Consequences
**Positive**
- Injection attempts are visible to reviewers and contained

**Negative / costs accepted**
- Scanning cost

## Enforcement
- Context builders wrap untrusted inputs automatically from the spec's `untrusted_inputs`
- Evaluation suite includes adversarial documents

## Guidance for agents
Declare untrusted inputs; let the builder wrap them.

**Do**
```yaml
untrusted_inputs: [document_text]
```

**Don't**
```yaml
inputs={'document_text': text}  # passed raw without declaration
```

## Revisit when
New injection techniques require additional detection.

## Related
- ADR-025
- ADR-049
