---
id: TASK-2231
title: N-02-T23 portal envelope routes live (POR-06, DocuSeal)
spec: SPEC-381  # signatures and engagement letters; N-02 §3.4
acceptance_criteria: [AC-10, AC-11, AC-12, AC-16]
risk_zone: red
status: in-review
epic: N-02
plan_key: N-02-T23
branch: s17-n02-t23
created: 2026-10-30
updated: 2026-10-30
---

## Objective
Replace the POR-06 portal stubs with live routes on the DocuSeal provider (ADR-342): list (to
sign, signed) through `scope_only`, view, masked pages, viewed and progress, ERSD consent per
signer, a one-time signing session for the named signer, a return that polls before answering,
decline and withdraw, and an audited signed-copy download.

Acceptance (backlog row): "Owen Calder signs E13 on staging through the demo account, the return
page shows Completed only after the poll, and Jonah Feld cannot open Claire's session."

## Plan (red)
- **Who:** the person's own `contact` signer row (engagements' `contact_ids_of_user`), then
  `portal_envelopes.*` on the envelope's engagement and work item (`scope_only`); any refusal is
  404 (INV-4). Client-level envelopes stay refused until the matrix has a client portal scope.
- **ERSD:** the firm's newest `esign_disclosures` version into `esign_acceptances` once per
  signer; a session needs it.
- **Session:** a `signing_sessions` row, five minutes to start, presentation `redirect`
  (DocuSeal refuses framing, DEC-1278). Refusals: `declined`, `envelope_not_open`,
  `verification_failed`, `mfa_required`, `not_your_turn`, `before_date_as_of` (firm zone),
  `esign_consent_required`; 503 `provider_unavailable` with the provider flag off. The URL is a
  bearer link: read per session through a new `EsignProvider.signing_url`, `no-store`, never
  stored (the idempotency record keeps the session id only).
- **Return URL:** `EnvelopeSpec.return_url`, sent as each DocuSeal submitter's
  `completed_redirect_url` (Sprint 15's finding).
- **Return:** parameters ignored; `envelope_poll` runs inline before the answer; `outcome`
  `signed` only after that poll; the workflow is hinted.
- **MFA:** `AuthContext.portal_second_step` from the portal session (second step or trusted
  device), or the IdP's `mfa_at`.
- **Decline/withdraw:** portal declines withdraw while Declined; provider declines are final.
- **Pages:** evidence `signer_page` (masked rendition only, read logged) for a proven signer.
- **Signed copy:** combined document plus the provider's evidence pages, merged in the isolated
  child; `signed_copy.downloaded` per download.
- **Tests:** HTTP acceptance on the fake provider (Owen signs, Completed only after the poll;
  Jonah never reaches Claire's session), refusals, decline/withdraw, download audited; the stub
  contract test updated for live portal routes.
- **Rollback:** `signatures.envelopes` off hides every route; `signatures.esign_provider` off
  stops sessions.

## Progress log
- 2026-10-30: plan written; built (DEC-1283). No migration: 0292's tables cover it. Tests
  written, run at the end review (Ayush: build first, test last). The staging walk with the demo
  account needs the DocuSeal install connected on staging.
