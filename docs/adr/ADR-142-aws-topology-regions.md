---
id: ADR-142
title: AWS production topology - us-east-2 primary, us-west-2 DR
status: accepted
date: 2026-10-20
deciders: ayushkbhatia
risk_zone: red
---

> **Instructions for coding agents**
> - Accepted ADRs are binding. Code that contradicts one must not be written.
> - If a task seems to require breaking an ADR, propose a new ADR that supersedes it.
> - Never edit an accepted ADR. Propose a new one that supersedes it.

## Context
Nothing is deployed. ADR-021 says only "a US region" and repo examples use us-east-1, while the designed copy (ADM-06, PLT-01) says storage in Ohio and backup in Oregon. Staging, KMS, SES, Bedrock and WorkOS setup all wait on the region and account layout. Plan decision DEC-03 settles this; this ADR is P-55 in the plan's ADR backlog.

## Decision
- **Regions.** us-east-2 primary, us-west-2 DR. us-east-1 is used only for global edge services (CloudFront, its ACM certificates, WAF) and as a Bedrock US Geo destination. Tenants are pinned to a US region.
- **Accounts.** AWS Organizations with Control Tower: `management`, `log-archive`, `audit`, `shared`, `staging`, `production` (and an optional `sandbox` that never holds data). Terraform state lives in S3 with locking, in `shared`; budget alarms are set.
- **Compute.** ECS Fargate: one backend image, one service per Temporal work class, a ClamAV service, and one-off migrate and bootstrap tasks.
- **Database.** RDS for PostgreSQL 17, Multi-AZ, with pgvector and pg_trgm, 35-day point-in-time recovery, cross-region backups to us-west-2, and a vault-locked copy in `audit`.
- **Storage and keys.** S3 Object Lock in GOVERNANCE mode for evidence and documents (bypass only through a dual-control break-glass role); COMPLIANCE mode for archive seal manifests and signature and consent packages. One multi-Region KMS key per firm, created by `worker-keyops`, with deletion under dual control.
- **Services.** Temporal Cloud with a namespace per environment and PrivateLink in production. ClamAV as an internal service on plaintext. CloudFront plus WAF at the edge. SES in us-east-2 for outbound email; firm-mailbox intake through Microsoft Graph.

## Options considered
### Option A: us-east-2 primary, us-west-2 DR with Control Tower accounts — chosen
- Pros: matches the designed copy; avoids us-east-1's shared blast radius; unblocks staging.
- Cons: a few services must still sit in us-east-1.

### Option B: us-east-1 (repo examples)
- Pros: broadest service availability.
- Cons: contradicts the designed copy on ADM-06 and PLT-01.
- Why rejected: the plan resolves conflict C-16 in favour of the design.

### Option C: self-hosted orchestration or EKS
- Pros: more control.
- Cons: more to operate for a solo builder.
- Why rejected: Fargate and Temporal Cloud cover the need.

## Consequences
**Positive**
- Region, accounts and services are fixed for Terraform, KMS, SES and Bedrock work.

**Negative / costs accepted**
- The region policy and IAM must allow the three Bedrock US Geo regions.

**Follow-up work created**
- Code: Terraform landing zone, bootstrap and environments (epic Q-01, S0-S5; Q-01-T01, T03); `firms.region` column and settings validation refusing non-US regions (Q-01, S0-S5).
- Specs: deploy-time region settings `ABACUS_S3_REGION`, `ABACUS_BEDROCK_REGION` and the SES region (Q-01, S0-S5).
- Glossary: none.
- Matrix: none.
- Registry: first `docs/operations/provider-terms.yaml` entry records `region: us-east-2` (Q-02, S0-S13).

## Enforcement
- [x] Architecture / dependency rule in CI: Terraform plan runs in infra CI; apply from `main` only.
- [x] Test: settings validation refuses non-US regions.
- [x] Hook or protected path: organisation-level region policy.
- [ ] Advisory only: none.

## Guidance for agents
Treat us-east-2 as the home of every regional resource, with us-west-2 as the replica. Put only CloudFront, its ACM certificates and WAF in us-east-1. Never write a spend figure into code or docs.

**Do**
```hcl
provider "aws" { region = "us-east-2" }
```

**Don't**
```hcl
provider "aws" { region = "us-east-1" }  # for a regional resource
```

## Revisit when
A customer requires a different residency, or a pinned model is unavailable through the US Geo profiles.

## Related
- Plan: P-55 (`docs/plan/09-decisions-adrs.md` section 9.4.2); DEC-03; D-OPS-02 to D-OPS-11; ch06 Appendix B; C-16.
- Extends ADR-021: its Decision clause "AWS in a US region" is fixed to us-east-2 with us-west-2 DR, and its "Separate AWS accounts for development, staging and production" is refined to the Control Tower layout above. Nothing else in ADR-021 changes.
- Extends ADR-087 (separate accounts per environment) with the account list, and ADR-096 ("a second US region") by naming it us-west-2.
