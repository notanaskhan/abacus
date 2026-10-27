---
id: ADR-149
title: E-signature - record mode first, then DocuSign embedded with ID Verification behind an EnvelopeProvider port
status: accepted
date: 2026-10-27
deciders: ayushkbhatia
risk_zone: red
---

> **Instructions for coding agents**
> - Accepted ADRs are binding. Code that contradicts one must not be written.
> - If a task seems to require breaking an ADR, propose a new ADR that supersedes it. Never work around it silently.
> - Never edit an accepted ADR. Propose a new one that supersedes it.

## Context
**Accept by 2026-12-04.** SPEC-025 Q2 says the engagement letter is signed in the firm's own tool and Accrued only records it. Fourteen journeys still need an envelope screen (SIG-02) and portal signing (POR-06). The vendor clock (DocuSign Go-Live review, ID Verification terms, counsel's ESIGN/ERSD view) sets the decision date; the go/no-go is task F-09-T41 on Fri 2026-12-04. Plan decision DEC-25 settles the path; this ADR is P-26. Without it, 8879 forms and letters have no signature route before the 2027 extension season.

## Decision
- **Record mode first.** Accrued imports the evidence package from the firm's own provider; it does not run a ceremony.
- **Then DocuSign embedded signing with DocuSign ID Verification (KBA)**, live before the 2027 extension season, behind an `EnvelopeProvider` port.
- **8879 family.** KBA is required and SMS is refused. Three failed KBA attempts route to a handwritten signature, not a 24-hour lockout.
- **Send is human-only.** Envelope policies are data, not code.
- **Consent.** The ESIGN/ERSD consent is stored.
- **Native ceremony.** A native T16 ceremony with its own KBA vendor waits until 2028.
- **Counsel review is requested through F-09's engagement** (ESIGN and ERSD consent, Pub 1345 KBA). Accept-by is the DocuSign go/no-go, Fri 2026-12-04. If counsel has not answered by then, DEC-25 falls back to **record mode only** (Option C) until counsel does; the fallback never defaults into a ceremony.

## Options considered
### Option A: record mode, then DocuSign embedded + ID Verification — chosen
- Pros: lighter Pub 1345 burden (provider-hosted KBA); fits the first real tax season; honours "record, don't rebuild".
- Cons: depends on a vendor review and commercial terms.

### Option B: native ceremony plus a bought KBA vendor (ch. 02 D-12)
- Pros: full control of the ceremony.
- Cons: Accrued becomes the e-signature software for Pub 1345.
- Why rejected: heavier compliance load; deferred to 2028.

### Option C: record mode only
- Pros: no vendor dependency.
- Cons: leaves SIG-02 and POR-06 without a send path.
- Why rejected: it is the fallback if the 2026-12-04 go/no-go is no-go, not the plan.

## Consequences
**Positive**
- A signature route that does not make Accrued the e-signature software.

**Negative / costs accepted**
- Record mode alone is the 2027 route if DocuSign is no-go.

**Follow-up work created**
- Code: `modules/signatures`, the `EnvelopeProvider` port and the DocuSign adapter (EP-08; N-02-T09 S14, record-mode readiness N-02-T17 S15, adapter N-02-T18 S16).
- Specs: SPEC-025 Q2 amended; SIG-01/02, POR-06, ENG-04, TAX-12, AUD-21, ADM-05 follow.
- Glossary: add envelope, evidence package, record mode (`docs/product/glossary.md`).
- Matrix: `envelope.*` actions in `docs/architecture/permission-matrix.yaml` (N-02-T02, S13); no agent `envelope.send`.
- Registry: DocuSign as write class W7 in `write-capabilities.yaml` (ADR-150); DocuSign row in `docs/operations/provider-terms.yaml`.

## Enforcement
- [ ] Lint rule: none new.
- [ ] Architecture / dependency rule in CI: only `EnvelopeProvider` implementations call DocuSign hosts.
- [x] Test: KBA-failure path routes to handwritten signature; SMS is refused; agent principal cannot send.
- [x] Hook or protected path: the matrix and `write-capabilities.yaml` are protected.
- [ ] Reviewer agent checklist item: no ceremony logic outside the port.
- [ ] Advisory only — reason: n/a

## Guidance for agents
Until accepted, build record mode only. Never add a native signing ceremony or an SMS factor.

**Do**
```
provider: EnvelopeProvider = registry.envelope_provider(firm)   # 'external' | 'docusign'
```

**Don't**
```
requests.post("https://na1.docusign.net/...")   # outside the adapter
```

## Revisit when
A design partner requires a native ceremony (2028), or the Fri 2026-12-04 go/no-go is no-go.

## Related
- ADRs: supersedes SPEC-025 Q2's "signed in the firm's own tool" stance in part; ADR-041 (webhook as hint, polling as truth) applies.
- Plan: P-26; DEC-25; ch. 06 D-OPS-17 and §6.3; ch. 02 D-12 (overridden by X-3).
- Specs: SPEC-025 Q2 (superseded in part).
