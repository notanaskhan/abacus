---
id: TASK-2234
title: N-02-T24 registrations (MFA, Sign to-do, CSP, notification and email kinds)
spec: SPEC-381  # N-02 §4.8; P-08-T13, P-08-T17; C16
acceptance_criteria: [AC-10]
risk_zone: red
status: in-review
epic: N-02
plan_key: N-02-T24
branch: s17-n02-t24
created: 2026-10-30
updated: 2026-10-30
---

## Objective
N-02's registrations: the MFA floor for envelope signers, POR-02's Sign to-do, the provider's
CSP (DocuSeal: none), the integrations row (exists), C16 notification kinds and client email
keys, with every email's words as database content.

Acceptance (backlog row): "Claire's Sign to-do appears on POR-02, the firm CSP is unchanged, and
no email copy lives in code."

## Plan (red)
- `signatures/signer_facts.py`: `envelope_signer_mfa` (registered as `envelope_signer`) and
  `sign_todo`; `portal/home_sources/signatures.py` registers the `sign` to-do.
- Notifications: six kinds; catalogue lines for `envelope.completed`, `envelope.declined`,
  `envelope.expired` to the sender; the two new events emitted by the poll and the expiry.
- Communications: four client keys beside `signature_request`; no copy committed.
- CSP: no change (redirect, DEC-1278); a test pins that neither policy names DocuSeal.
- Tests: Claire's Sign to-do on her home and not on Jonah's for Claire's envelope; the floor
  predicate; the CSP; the keys registered with no committed copy; the catalogue pins.

## Progress log
- 2026-10-30: built (DEC-1286). Tests written, run at the end review. Human to-do: import the
  notification templates and publish the client keys per environment before the provider flag.
