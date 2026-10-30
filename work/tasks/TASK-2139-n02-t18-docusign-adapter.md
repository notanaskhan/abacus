---
id: TASK-2139
title: N-02-T18 DocuSign adapter behind the EsignProvider port (W7)
spec: SPEC-381
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: red
status: in-review
epic: N-02
plan_key: N-02-T18
branch: s16-n02-t18
created: 2026-10-30
updated: 2026-10-30
---

## Objective
DocuSign behind the provider port. Acceptance (backlog row): "Against the demo account a
two-signer envelope is created exactly once under a retried send and its request and response
evidence is stored write-once."

## Plan
- `signatures/docusign.py`: JWT grant (RS256, key from the sealed install secret), create with
  captive recipients, routing (sequential order or parallel group), tabs from placed fields or
  anchors, DF-11 identity (KBA, email, firm sign-in; never SMS), the `accrued_idempotency` custom
  field read back before any create, status, combined document, certificate, signer evidence from
  audit events, remind, void; DocuSign hosts only.
- `signatures/docusign_firm.py`: the firm's adapter only when `signatures.docusign` (new kill
  switch flag), the W7 entry `enabled` and a connected `docusign` install all allow.
- `provider.provider_for(tenant)`: the process-wide provider (the fake) else the firm's;
  `envelope_send` records `envelope.provider_unavailable` and returns not sent when off.
- Send (N-02-T20) now emits `envelope.send_approved`, held to +10 s and bound to the grant; the
  relay consumes the grant and `on_send_approved` starts EnvelopeWorkflow.
- `evidence.version_content`, `integrations.connected_integration` added to the APIs.
- Tests: `tests/unit/signatures/test_n02t18_docusign_adapter.py` (mock transport).

## Human to-dos
- W7 stays declared and disabled: `WriteCapabilityEntry.enabled` is `Literal[False]` and the A-02
  independent tests pin it. Opening W7 is ADR-150's next schema version (a human decision with
  counsel and the provider terms row), then `enabled: true` for `esignature_envelope_send`.
- The demo-account run of the acceptance needs a DocuSign developer account, the install row and
  its sealed secret (integration key, user id, account id, base URI, OAuth host, RSA key).
- Q-01's egress firewall must list `docusign.ALLOWED_HOSTS` when W7 opens.

## Progress log
- 2026-10-30: built; adapter unit tests pass (3). Integration and replay tests at the end review.
