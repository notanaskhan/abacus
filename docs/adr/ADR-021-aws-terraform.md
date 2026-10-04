---
id: ADR-021
title: AWS in a US region, defined in Terraform
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
Firms' IT reviewers need one clear trust boundary and mature compliance controls. With two application languages, single-language infrastructure tooling no longer applies.

## Decision
All infrastructure runs on AWS in a US region: ECS Fargate for API and workers, managed PostgreSQL, S3, KMS, Secrets Manager, CloudFront for the SPA. Separate AWS accounts for development, staging and production. Infrastructure is defined in Terraform. Connector credentials use KMS envelope encryption. External processors — the model provider, Temporal Cloud, the identity provider, Sentry — are documented, and data sent to them is minimised and encrypted where possible.

## Options considered
### AWS + Terraform — chosen
- Pros: Mature compliance; widely understood
- Cons: AWS complexity
- Chosen.

### PaaS hosting
- Pros: Faster start
- Cons: Weaker compliance story; migration later
- Rejected.

### AWS CDK
- Pros: Code-based
- Cons: Language split after ADR-009
- Rejected.

## Consequences
**Positive**
- One trust boundary for security review

**Negative / costs accepted**
- Operational complexity of AWS

**Follow-up work**
- Subprocessor register for SOC 2

## Enforcement
- All infrastructure changes go through Terraform plans reviewed in pull requests
- Policy checks in CI reject public buckets, unencrypted storage and overly broad IAM
- Protected path: `infra/` requires human approval

## Guidance for agents
Change infrastructure through Terraform only.

**Do**
```bash
terraform plan  # reviewed in the PR
```

**Don't**
```bash
aws s3api put-bucket-policy ...  # manual console or CLI change
```

## Revisit when
A customer requires a different region or cloud.

## Related
- ADR-016
- ADR-017
