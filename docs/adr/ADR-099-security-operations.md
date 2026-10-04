---
id: ADR-099
title: Security operations baseline
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
SOC 2 and customer due diligence require demonstrable security operations from the start.

## Decision
Audit logging across all AWS accounts shipped to a separate locked log-archive account; threat detection and configuration monitoring enabled; human access through SSO without long-lived keys, with MFA; base images rebuilt weekly and critical vulnerabilities fixed within a defined window; dependency updates via automated pull requests through the full gate suite; quarterly access reviews; external penetration testing before larger deals and annually; SOC 2 via compliance automation with controls mapped to these ADRs.

## Options considered
### Baseline from day one — chosen
- Pros: Audit-ready; lower breach risk
- Cons: Operational overhead
- Chosen.

## Consequences
**Positive**
- Security posture demonstrable to auditors and customers

**Negative / costs accepted**
- Ongoing operational work

**Follow-up work**
- Control-to-ADR mapping

## Enforcement
- Infrastructure policy checks enforce logging and detection configuration
- Long-lived IAM user keys denied by policy

## Guidance for agents
Access AWS through SSO sessions.

**Do**
```bash
aws sso login --profile prod-readonly
```

**Don't**
```bash
aws configure  # long-lived access keys
```

## Revisit when
Never expected to change.

## Related
- ADR-021
- ADR-028
