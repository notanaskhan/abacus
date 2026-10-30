---
id: ADR-342
title: E-signature provider - DocuSeal (cloud) replaces DocuSign behind the EsignProvider port
status: accepted
date: 2026-10-30
deciders: ayushkbhatia
risk_zone: red
---

> **Instructions for coding agents**
>
> - Accepted ADRs are binding. Code that contradicts one must not be written.
> - If a task seems to require breaking an ADR, propose a new ADR that supersedes it. Never work around it silently.
> - Never edit an accepted ADR. Propose a new one that supersedes it.

## Context

ADR-149 (P-26, DEC-25) chose record mode first, then DocuSign embedded signing with DocuSign ID Verification behind an `EnvelopeProvider` port. Nothing on the DocuSign side was ever set up: the developer account (F-09-T08) was never opened, so the adapter (N-02-T18, #775) and the status poll (N-02-T19, #776) exist only against the fake provider, and N-02-T06 (the DF-12 presentation spike) and the S17 rows N-02-T22 to T25 wait on an account.

On 2026-10-30 the builder decided DocuSign is too expensive for Accrued's stage, and that building our own ceremony and identity check is too expensive and too slow (ADR-149 Option B stays deferred to 2028). The commercial comparison and every amount are in the vault, never in git.

DocuSeal (docuseal.com) is an open-source (AGPL) e-signature product with a hosted API. Read from its public documentation on 2026-10-30:

- **API.** REST with an `X-Auth-Token` API key. Templates from PDF, DOCX or HTML, with fields placed by text tags or coordinates. Submissions are created from a template or one-off from a document, and each submitter carries `external_id` and `metadata`. Documents (partial or final) and an audit log are fetched per submission. Hosts: a global host and an EU host. A free sandbox allows unlimited API and embedding tests.
- **Signing.** Each submitter has a signing URL `/s/{slug}`. The documented embed is a web component loaded from DocuSeal's CDN, with React, Vue and Angular wrappers, a completed-redirect URL, and completed and declined events.
- **Webhooks.** `form.viewed`, `form.started`, `form.completed`, `form.declined`, `submission.created`, `submission.completed`, `submission.expired` and `submission.archived` are listed. Failed deliveries are retried for 48 hours. Payloads carry the submission's `audit_log_url` and document URLs. No signature scheme and no event id are documented.
- **Lifecycle.** Submissions can be updated (expiry, archived) and archived. There is no void verb and no idempotency key.
- **Identity.** SMS verification, ID-document verification and knowledge-based authentication (KBA) are offered on the cloud Pro tier. DocuSeal states that its KBA meets the IRS identity requirement for remote Form 8879 signing. It publishes neither the question source, the pass threshold, nor the attempt and lockout behaviour, and KBA is switched on per account by DocuSeal support.
- **Self-hosting.** The free open-source edition has no embedded signing, no SMS and no KBA. The on-premises Pro edition adds embedding and white-labelling, but KBA is not listed for it.

The `signatures` module already speaks to providers only through `EsignProvider` (`provider.py`: `create_and_send`, `status`, `completed`, `remind`, `void`). EnvelopeWorkflow, record mode, the SIG-01 and SIG-02 backends and the fake are provider-neutral, so a provider change is an adapter change.

## Decision

- **Provider.** DocuSeal's hosted API (cloud, Pro tier) replaces DocuSign as the provider behind `EsignProvider`. Everything else in ADR-149 carries over unchanged and is restated here so ADR-149 can be superseded whole:
  - **Record mode first.** Accrued imports the evidence package from the firm's own provider; record mode is the fallback for every envelope purpose and never defaults into a ceremony.
  - **Send is human-only.** Envelope policies are data, not code.
  - **ESIGN/ERSD consent is stored** (`esign_acceptances`) before any signing session opens.
  - **8879 family.** KBA is required and SMS is refused. Three failed KBA attempts route to a handwritten signature, not a lockout window.
  - **Native ceremony** with its own KBA vendor waits until 2028.
- **Self-hosting is deferred.** The open-source edition cannot serve the 8879 path, and running a signed-document service ourselves adds an app, a datastore and a pen-test surface. The port keeps self-hosting a configuration change if cost or data location later require it.
- **Presentation (DF-12).** The portal loads no provider script, so DocuSeal's web component is refused. The ceremony is a same-tab redirect to the submitter's signing URL, fetched only when `POST signing-session` runs after portal MFA and ERSD consent, with the completed redirect set to `/sign/$envelopeId/return`. The return page confirms nothing until the poll does. N-02-T06 settles the URL lifetime and whether a plain iframe is possible; if the signing URL is long-lived, Accrued never shows or emails it, and the session route re-fetches it each time.
- **Firm-branded mail (DEC-59).** Submitters are created with DocuSeal's own email and SMS sending off. Every client message (request, reminder, signed copy) is Accrued's, from database templates. DocuSeal appears only as "via DocuSeal" in evidence.
- **Identity for the 8879 family.** DocuSeal KBA is used only after DocuSeal confirms the method in writing (question source, pass threshold, attempts, SSN and ITIN handling, failure events) and counsel accepts it against Pub 1345 (F-09-T92). If both are not in hand by M8 criterion (c), the 8879 family stays on record mode and the handwritten path for 2027; letters and consents still use DocuSeal, since they need ERSD consent and portal MFA, not KBA.
- **Status truth.** ADR-041 applies: a webhook is a hint, the poll is the truth. Because DocuSeal documents no webhook signature, a receiver is mounted only if N-02-T06 finds a verifiable secret, and only under ADR-152's amendment, retargeted from DocuSign Connect. Until then status is poll-only, as built in N-02-T19.
- **Mapping to the port.**
  - `void` is archive plus Accrued's own envelope state.
  - Idempotency is `external_id` = the envelope's signer id plus a re-read before any re-send, as T18 already does for retries.
  - `completed` downloads the combined document and the audit log at once and stores them write-once in COMPLIANCE storage. Provider URLs are never kept as evidence.
- **Names.** Code identifiers stay provider-neutral where they already are: W7 `esignature_envelope_send`, `EsignProvider`, `envelope_provider_calls`. The provider value `docuseal` is added to `envelopes.provider` in an expand-only migration (`docusign` is removed later by a contract migration once no row can hold it). The `signatures.docusign` flag is replaced by `signatures.esign_provider` in the adapter rework. The integrations catalogue key becomes `docuseal`.

## Options considered

### Option A: DocuSeal cloud (Pro) behind the port, record mode first — chosen

- Pros: costs a fraction of DocuSign and is within budget (amounts in the vault); free sandbox, so N-02-T06 and the adapter can be tested today; KBA offered for the 8879 family; the existing port absorbs the change.
- Cons: KBA method unpublished; no documented webhook signature, void or idempotency key; younger vendor whose compliance reports (SOC 2) and US hosting are unconfirmed.

### Option B: DocuSign embedded with ID Verification (ADR-149)

- Pros: established vendor; KBA long used for 8879.
- Cons: cost.
- Why rejected: too expensive for Accrued's stage (builder, 2026-10-30).

### Option C: self-hosted DocuSeal

- Pros: no per-document fee on the open-source edition; signed documents stay in our AWS account.
- Cons: the free edition has no embedding, SMS or KBA; on-premises Pro does not list KBA; Accrued would operate and pen-test a signed-document service.
- Why rejected: deferred, not refused. Revisit triggers below.

### Option D: record mode only

- Pros: no vendor.
- Cons: SIG-02 and POR-06 have no send path.
- Why rejected: it remains the fallback, not the plan.

### Option E: native ceremony with a bought KBA vendor

- Why rejected: unchanged from ADR-149; deferred to 2028.

## Consequences

**Positive**

- The provider path is unblocked without a vendor review or a long contract.
- The 8879 decision is isolated: letters and consents go live on DocuSeal whatever happens to KBA.

**Negative / costs accepted**

- More logic stays on Accrued's side (void as archive, idempotency by re-read, poll-only status, evidence copied at completion).
- Until DocuSeal's KBA is confirmed in writing and accepted by counsel, M8 criterion (c) is open.

**Follow-up work created**

- Plan rows re-scoped with this ADR (backlog and epic task files): N-02-T06, T18, T19, T24, T25, T39, T44 and T46; F-09-T08, T11, T28, T41, T63, T64, T65, T81, T92, T97, T121, T123, T125, T158 and T214. The N-02 and F-09 epic specs carry an amendment note. Elsewhere in the plan, "DocuSign" reads as "the e-signature provider (DocuSeal, ADR-342)", "DocuSign demo" as "the DocuSeal sandbox" and "DocuSign ID Verification" as "DocuSeal KBA".
- Code (N-02-T18 rework):
  - a DocuSeal adapter replaces `signatures/docusign.py`
  - `docusign_firm.py` and `integrations/secrets.py` move to an API-key install under catalogue key `docuseal`
  - the `_capabilities.py` W7 adapter key changes
  - the expand-only `envelopes.provider` migration
  - the flag rename
  - `banned_patterns` host exclusions move to the DocuSeal hosts
  - the `builder.py` draft provider changes
- Code (N-02-T19 rework): `status_poll.py` polls DocuSeal submissions.
- Docs: ADR-152's proposed amendment retargeted to a DocuSeal receiver, or withdrawn if T06 finds no verifiable secret. Also `docs/contracts/c7-envelopes.md`, `docs/operations/sub-processors.yaml` and `provider-terms.yaml` (DocuSeal row, counsel second approver), and the M8 gate's c2 and c3 rows.
- On acceptance: ADR-149's status becomes `superseded by ADR-342`, and DEC-25's artefact names ADR-342.

## Enforcement

- [ ] Lint rule: none new.
- [x] Architecture / dependency rule in CI: only `EsignProvider` implementations call provider hosts (`banned_patterns` host rule, moved to DocuSeal's hosts in the rework).
- [x] Test: KBA-failure path routes to a handwritten signature; SMS is refused; an agent principal cannot send; a retried send creates one submission.
- [x] Hook or protected path: the matrix and `write-capabilities.yaml` are protected.
- [ ] Reviewer agent checklist item: no provider script in the portal; no provider URL stored as evidence.
- [ ] Advisory only — reason: n/a

## Guidance for agents

Accepted on 2026-10-30 by ayushkbhatia. The N-02-T18 rework replaces `docusign.py` with the DocuSeal adapter; do not extend `docusign.py`. Until that rework lands, keep building record mode and the provider-neutral parts.

**Do**

```
provider = await provider_for(tenant_id)   # fake, record, or the firm's DocuSeal install
```

**Don't**

```
httpx.post("https://api.docuseal.com/submissions", ...)   # outside the adapter
<script src="https://cdn.docuseal.com/js/form.js">      # in the portal
```

## Revisit when

- DocuSeal cannot confirm its KBA method, or counsel rejects it for Pub 1345.
- Document volume makes on-premises Pro cheaper than cloud per-document fees.
- DocuSeal cannot produce a security report acceptable to design partners' vendor reviews.
- A design partner requires a native ceremony (2028).

## Related

- ADRs: supersedes ADR-149 (P-26); ADR-041 (webhook as hint, polling as truth); ADR-150 (write capabilities, W7); ADR-152 (unauthenticated operational routes; amendment to retarget).
- Plan: P-26; DEC-25; DEC-1275; DF-11; DF-12; DEC-59.
- Specs: SPEC-025 Q2 (superseded in part, unchanged by this ADR).
