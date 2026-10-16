---
id: ADR-114
title: A model route carries client data only with recorded, current provider terms
status: accepted
date: 2026-10-16
deciders: Founder
risk_zone: red
---

> **Instructions for coding agents**
> - Accepted ADRs are binding. Code that contradicts one must not be written.
> - If a task seems to require breaking an ADR, **stop** and raise it. Never work around it silently.
> - Never edit an accepted ADR. Propose a new one that supersedes it.

## Context
ADR-031 says client data reaches a model provider only under zero-retention and no-training terms. ADR-112 keeps every real model on synthetic firms until those terms are recorded "as an ADR". ADR-113 says client data may use only Bedrock, in our AWS account and in a US region.

Nothing yet says **which** terms count, **where** they are recorded, or **how code knows** they are in place. Without that, lifting the boundary (SPEC-036) would depend on someone remembering a contract. Terms also change, and a provider can amend them or retire a service.

## Decision
1. **A route may carry client data (Restricted or Confidential, ADR-031) only when the provider terms register holds a current entry for it.** The register is `docs/operations/provider-terms.yaml`, a protected policy file that only the founder edits. Each entry records:
   - the route and provider;
   - the documents relied on, each with its title, version or date, and the date accepted;
   - **training:** inputs and outputs are not used to train or improve models;
   - **retention:** prompts and outputs are not stored beyond processing. Any exception (abuse monitoring, legal hold) is named with its maximum period (Q1);
   - **region:** where processing happens, which must be in the US (ADR-021, ADR-113);
   - **subprocessors** that may see the data;
   - **breach notice:** the provider's notification commitment, matching ADR-097's timelines;
   - `approved_by: founder`, `approved_on`, and `review_by` (at most 12 months later).
2. **Only Bedrock, in our AWS account, is eligible** for client data (ADR-113). The direct Anthropic API stays limited to synthetic data and evaluations, whatever its register entry says.
3. **Code enforces it.**
   - Settings validation refuses to enable client data on a route unless the register has an entry for that route whose `review_by` hasn't passed. The register is compiled into code (`abacus_tools.codegen.provider_terms`, like the permission matrix), and a test fails if they differ.
   - At boot, an entry past `review_by` disables client data on its route. Real firms then get the boundary refusal; synthetic firms are unaffected.
4. **Firms are told.** The firm-facing list of subprocessors and AI providers is generated from the register. A firm opts in against that disclosure (SPEC-036), so the version a firm accepted is known.
5. **Any change to the terms is a new register entry**, never an edit to an old one. A material change (training, retention, region) requires firms to opt in again (SPEC-036 Q4).

## Options considered
### Option A: register file, compiled and checked by code — chosen
- Pros: one source for code, the disclosure and audit; expiry is enforced; the history is in git.
- Cons: the founder keeps a YAML file current.

### Option B: this ADR alone lists the terms
- Pros: simple.
- Cons: accepted ADRs can't be edited, so every change would need a superseding ADR. Code can't read an ADR, and it has no expiry.
- Why rejected: the terms change more often than decisions do, and nothing would enforce them.

### Option C: per-firm contracts recorded in the database
- Pros: matches how some firms want it.
- Cons: the provider's terms are ours, not each firm's; storing them per firm repeats the same facts and lets them drift.
- Why rejected: a firm's own consent belongs in SPEC-036's opt-in, which points at the register version.

## Consequences
**Positive**
- Lifting the boundary has a concrete, checkable precondition.
- An expired or withdrawn term turns client data off without a deploy.

**Negative / costs accepted**
- The founder owns the register and its annual review. A missed review turns AI off for real firms.
- A provider's standard terms may not meet item 1 without an enterprise agreement (Q1, Q2).

**Follow-up work created**
- SPEC-036 (data boundary for real firms), and its tasks: the register and its codegen, settings validation, the generated disclosure.
- C2: the Bedrock route in our AWS account (needs AWS details).
- Superseding ADR-112 once SPEC-036 is accepted.

## Enforcement
- [x] Test: the register compiles, every entry has every field, and the compiled module matches the YAML.
- [x] Test: settings with client data on a route without a current entry fail validation; `direct` is never allowed.
- [x] Hook or protected path: `docs/operations/provider-terms.yaml` is a policy file (protected).
- [ ] Reviewer agent checklist item: a change touching the AI gateway's routes names the register entry it relies on.

## Guidance for agents
Never enable a real route for a firm that isn't synthetic unless the register holds a current entry for that route and SPEC-036's opt-in applies. Don't read the register at request time: use the compiled module.

**Do**
```python
if not terms.covers(route, today):  # compiled from provider-terms.yaml
    raise DataBoundaryRefused(...)
```

**Don't**
```python
if settings.environment == "production":  # environment isn't a contract
    allow_client_data = True
```

## Revisit when
- A second provider or model family is needed for client data.
- A firm requires its own contract with the provider, or data residency outside the US.
- A regulator or SOC 2 auditor asks for a different record of subprocessors.

## Related
- ADRs: ADR-021, ADR-031, ADR-073, ADR-074, ADR-097, ADR-111, ADR-112, ADR-113.
- Specs: SPEC-026, SPEC-036.

## Open questions (resolved before acceptance)
All resolved: the founder approved every recommendation below on 2026-10-16.
- **Q1: retention exceptions.** Some provider terms allow keeping prompts briefly for abuse monitoring. *Recommendation:* allowed only if named in the entry with a maximum of 30 days, no human review of client content without our request, and no training. Otherwise the route isn't eligible.
- **Q2: which documents.** *Recommendation:* the AWS customer agreement and service terms for Bedrock, AWS's data processing addendum, and Bedrock's data-protection documentation, each recorded with the version you accepted. The founder confirms the actual documents and dates when entering them; this ADR doesn't assert what they say.
- **Q3: who may approve an entry.** *Recommendation:* the founder only, for now. Add a second approver (counsel) before the first paying firm.
