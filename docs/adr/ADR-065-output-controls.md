---
id: ADR-065
title: Output controls on agent-generated content
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
Agent output can leak data — by including out-of-scope figures in messages, or by embedding links and images that exfiltrate data when rendered.

## Decision
Model output is rendered as sanitised plain text; it is never rendered as HTML or markdown that loads external resources. External links are stripped unless allowlisted. Every outbound message is checked before sending for clients, entities, accounts or amounts outside the engagement's scope; violations are blocked and flagged.

## Options considered
### Strict output controls — chosen
- Pros: Closes rendering and messaging exfiltration
- Cons: Less rich formatting
- Chosen.

### Render model markdown
- Pros: Nicer display
- Cons: Image/link exfiltration risk
- Rejected.

## Consequences
**Positive**
- Output cannot exfiltrate data via rendering or messaging

**Negative / costs accepted**
- Plain formatting of agent text

## Enforcement
- Frontend renders agent text through a sanitising plain-text component only (lint rule)
- Outbound message scope checker runs in the send path; test with seeded out-of-scope values

## Guidance for agents
Send through the guarded message service.

**Do**
```python
await messages.send(ctx, draft)  # scope check runs before delivery
```

**Don't**
```python
await email.send(to, body=llm_output)
```

## Revisit when
Never expected to change.

## Related
- ADR-064
- ADR-031
