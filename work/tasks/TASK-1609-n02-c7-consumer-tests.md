---
id: TASK-1609
title: C7 consumer contract tests for N-02's screens (N-02-T04)
spec: SPEC-381
acceptance_criteria: [AC-5, AC-8, AC-16, AC-18]
risk_zone: amber
status: in-review
epic: N-02
plan_key: N-02-T04
branch: s13-n02-t04
created: 2026-10-27
updated: 2026-10-27
---

## Objective
Fail on a removed field, an unmasked IP or an unregistered status word in the SIG-01, SIG-02, POR-06 and ENG-04 view models.

## Plan
- `backend/tests/contracts/c7_n02/test_c7_stubs.py`: one action per route; firm and portal stub ordering; ADR-031; final verbs deny agent and system; agent drafts only; fresh MFA on reveal, policy and approval; `scope_only` on portal verbs; no `sms_code`; masked IP only; no TIN or SSN field; registry status words; reserved `signing_session` and `outcome`; DF-31 letter words.
- TypeScript fixture assertions follow with the SIG and POR fixtures (N-02-T11, T23).
- Rollback: revert.

## Progress log
- 2026-10-27: written; run in the batch pass.
