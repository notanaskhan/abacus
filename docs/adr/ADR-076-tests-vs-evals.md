---
id: ADR-076
title: Tests are deterministic; evaluations call real models
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
Mixing model calls into tests creates flaky, costly suites; burying evaluations in tests means they are rarely run or trusted.

## Decision
Tests never call real models; they use a fake model returning recorded, fixed responses. Evaluations always call the real, pinned model through the AI gateway in evaluation mode. The two live in separate directories and run in separate CI stages.

## Options considered
### Strict separation — chosen
- Pros: Reliable tests; meaningful evaluations
- Cons: Two harnesses
- Chosen.

### Real models in tests
- Pros: Realistic
- Cons: Flaky, slow, costly
- Rejected.

## Consequences
**Positive**
- A green test suite always means the same thing

**Negative / costs accepted**
- Fake model fixtures to maintain

## Enforcement
- Test configuration injects the fake model; network calls to model providers fail in test mode
- Evaluations live under `evals/` and run only via the evaluation runner

## Guidance for agents
Use the fake model in tests.

**Do**
```python
ai = FakeModel.from_fixture('screening/needs_revision_wrong_period.json')
```

**Don't**
```python
ai = Gateway(provider='live')  # in a unit test
```

## Revisit when
Never expected to change.

## Related
- ADR-019
- ADR-081
