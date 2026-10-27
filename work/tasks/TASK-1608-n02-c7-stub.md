---
id: TASK-1608
title: C7 envelope service v1 stub (N-02-T03)
spec: SPEC-381
acceptance_criteria: [AC-1, AC-4, AC-5, AC-7, AC-10, AC-13, AC-16, AC-18]
risk_zone: red
status: in-review
epic: N-02
plan_key: N-02-T03
branch: s13-n02-t03
created: 2026-10-27
updated: 2026-10-27
---

## Objective
Contract first for SIG-01, SIG-02, POR-06 and ENG-04: classified models, 501 routes under one action each, the signatures.api slots, the generated client.

## Plan
- `signatures/contract.py`: 19 firm routes (`/v1/envelopes*`, `/v1/envelope-policies*`) and 11 portal routes (`/v1/portal/envelopes*`); `IdentityMethod` has no `sms_code`; IPs masked; provider fields and `signing_session` reserved.
- `engagements/letter_contract.py`: 8 composer routes under `/letter/composer` (the record `PUT /letter` stays).
- `signatures/api.py`: `ROUTERS`, `register_envelope_source`, `envelope_summary_for`, `envelope_gate_facts` (bodies in N-02-T09).
- Status words: `envelope_signer` (T03), `letter` (DF-31, written here for the stub; T05 records its screens).
- `make regenerate`; error catalogue; contract doc status.
- Rollback: revert; the flag stays off.

## Progress log
- 2026-10-27: built; 38 C7 paths in the OpenAPI document; tests in N-02-T04 and the batch pass.
