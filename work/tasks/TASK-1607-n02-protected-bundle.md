---
id: TASK-1607
title: Signatures protected bundle, matrix, flag and fresh-MFA rows (N-02-T02)
spec: SPEC-381
acceptance_criteria: [AC-9, AC-16, AC-18]
risk_zone: red
status: in-review
epic: N-02
plan_key: N-02-T02
branch: s13-n02-t02
created: 2026-10-27
updated: 2026-10-27
---

## Objective
The signatures section of the matrix, the letter rows, `signatures.envelopes`, and the registers that go with them, so the C7 stub can declare its actions.

## Plan
- `permission-matrix/signatures.yaml` (new): `envelope.*`, `signer.reveal_ip`, `envelope_policy.*`, `portal_envelopes.*` (the plan's `portal.envelopes.*`, DEC-139). Agent and system: `envelope.draft` only; every final verb denied.
- `permission-matrix/engagements.yaml`: `letter.read`, `letter.draft` (agent: draft), `letter.approve` (fresh MFA), `letter.send`, `letter.amend`; `letter.record` kept.
- `fresh-mfa-actions.yaml`: `signer.reveal_ip` (reveal), `envelope_policy.manage` (access_control), `letter.approve` (release).
- `feature-flags/signatures.yaml` (new): `signatures.envelopes`.
- Already on main, nothing to do: W7 `esignature_envelope_send` (disabled, `write-capabilities.yaml`, A-02-T15), the DocuSign sub-processor row (`sub-processors.yaml`). The plan's provider-terms row does not apply: that register is for model routes only (ADR-114). Solo edition: no CODEOWNERS; `modules/signatures` is red by zone, not a protected path.
- Deferred to N-02-T07: TABLE_OWNERS and insert-only registrations (the schema check requires the tables to exist).
- `make regenerate` (matrix, flags, generated security tests, TS actions).
- Rollback: revert; the flag stays off.

## Progress log
- 2026-10-27: built; generated I-AGENT-NEVER tests run in the batch pass.
