---
id: ADR-081
title: Per-agent evaluation suites and grading
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
Agent quality must be measured against the errors that matter, with confidence that means something.

## Decision
Each agent has an evaluation suite of synthetic, consented and firm-scoped production cases, covering normal paths, failure-taxonomy categories, adversarial inputs and regressions. Grading prefers deterministic checks, then rule-based checks, then model grading with a pinned, human-calibrated judge for subjective qualities, with periodic human sampling. Thresholds are weighted toward each agent's dangerous error. Confidence calibration is measured and drives routing thresholds. Key cases run multiple times and are judged on pass rate. Firm-specific cases stay within that firm.

## Options considered
### Structured evaluation — chosen
- Pros: Measures what matters
- Cons: Dataset upkeep
- Chosen.

### Ad hoc spot checks
- Pros: Easy
- Cons: No reliable signal
- Rejected.

## Consequences
**Positive**
- Agent quality is measurable and comparable over time

**Negative / costs accepted**
- Dataset curation effort

## Enforcement
- Each suite declares graders, thresholds and dangerous-error metric
- Consented data stored outside the repository in restricted storage

## Guidance for agents
Weight thresholds toward the dangerous error.

**Do**
```yaml
thresholds:
  needs_revision_recall: 0.97
  ready_precision: 0.85
```

**Don't**
```yaml
thresholds:
  accuracy: 0.9
```

## Revisit when
Never expected to change.

## Related
- ADR-047
- ADR-067
- ADR-076
