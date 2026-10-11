---
id: ADR-113
title: Client data uses Bedrock in-region only; the direct API is for synthetic data
status: accepted
date: 2026-10-11
deciders: Founder
risk_zone: red
---

> **Instructions for coding agents**
> - Accepted ADRs are binding. Code that contradicts one must not be written.
> - If a task seems to require breaking this ADR, **stop** and raise it.
> - Never edit an accepted ADR. Propose a new one that supersedes it.

## Context
ADR-073 makes the same model family reachable through Bedrock and Anthropic's API, with failover between them. For client data, where the data is processed matters more than availability.

## Decision
- **Client data uses Bedrock only**, inside our AWS account, restricted to In-Region or US Geo inference profiles. Global profiles are rejected by configuration validation.
- **When Bedrock is unavailable**, calls degrade and queue per ADR-072; they never fail over to another route.
- **The direct Anthropic API is for synthetic data and evaluations only.**
- **Route configuration** maps each tier to a pinned model ID per route, so changing route is configuration. A model is used for client data only once it's confirmed available in the allowed Bedrock profiles.
- **Revisit ADR-055's cost assumptions:** Bedrock doesn't support prompt caching with batch inference.

## Consequences
SPEC-010's failover between routes applies to synthetic data only. The agent specs' route lists and the gateway need a follow-up spec before client data flows.

## Related
Refines ADR-073. ADR-055, ADR-072, ADR-112.
