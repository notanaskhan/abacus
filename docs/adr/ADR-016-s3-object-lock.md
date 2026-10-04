---
id: ADR-016
title: Evidence files in S3 with Object Lock
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
Evidence immutability (ADR-004) should be guaranteed by storage, not only by application code.

## Decision
Evidence files and raw connector payloads are stored in S3 with Object Lock in governance mode, encrypted with KMS, keyed by SHA-256 content fingerprint, with all public access blocked. Access is through short-lived presigned URLs. Retention periods follow the engagement's retention policy; legal holds are supported.

## Options considered
### S3 Object Lock, governance mode — chosen
- Pros: Write-once storage; privileged override possible for genuine errors
- Cons: Override role must be tightly controlled
- Chosen.

### Compliance mode
- Pros: Cannot be overridden even by administrators
- Cons: No recovery from mistakes
- Deferred; revisit when customers require it.

### Plain S3
- Pros: Simple
- Cons: Immutability depends on code
- Rejected.

## Consequences
**Positive**
- Immutability guaranteed at the storage layer
- Duplicate uploads deduplicate by fingerprint

**Negative / costs accepted**
- Retention configuration must be correct

## Enforcement
- Terraform configures Object Lock, KMS and public-access blocks; CI policy check rejects changes that weaken them
- Governance-override permission held by a single break-glass role, alarmed when used
- Test: upload stores under the content fingerprint; overwrite attempt fails

## Guidance for agents
Store through the evidence storage service.

**Do**
```python
key = await evidence_storage.put(ctx, content)  # returns sha256-addressed key
```

**Don't**
```python
s3.put_object(Bucket=b, Key=f'{name}.pdf', Body=content)
```

## Revisit when
A customer contractually requires compliance-mode retention.

## Related
- ADR-004
- ADR-021
