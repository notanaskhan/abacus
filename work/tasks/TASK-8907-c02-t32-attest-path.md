---
id: TASK-8907
title: "C-02-T32: Attest CAS path"
spec: SPEC-000
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: red
status: in-review
branch: s53-c02t32
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-23
updated: 2026-11-23
plan_key: C-02-T32
---

## Objective
classify_entry holds every attest entry, Send to client for approval through A-06's approve-and-send (C18 kind proposed_entry) to the approver of record, client decision to client_approved, posting refused attest_client_posting_refused, Recorded by client with evidence or a sync match (touches R-02's POR-08). Acceptance: the attest client's entries reach POR-08, become Client approved and then Recorded by the client, and no posting batch can include them.

## Done
- adjustments/attest_path.py: recipient_for (attest → approver of record, resolved or enforced; unknown attest reads attest), check_record (attest entry recorded only after client_approved; a match_ref must be one code finds), ledger_matches (register lines of the entry's month and the next, every account for the same amount in one ledger transaction, qbo:<txn id>; authorised on the engagement), matching_txns (pure), recorded_label
- approve-and-send: recipient_contact_id optional, routed through recipient_for; record-external runs check_record; new GET /v1/proposed-entries/{id}/ledger-matches
- Already on main and verified, not rebuilt: classify_entry with attest_client (close_approvals._classify), batch-within-policy refusal, posting refusal at registry/switches/batch (attest_client_posting_refused), R-02's client decision applier to client_approved (POR-08 e)
- Error codes catalogued; route introspection regenerated; docs/contracts/adjustments.md section
- tests/unit/adjustments/test_c02t32_attest_path.py (14 pass)

## Progress log
- `2026-11-23` — Built in the S53 sequential stack (DEC-5909). make generate at the end pass (new route, optional field).

## Plan (red)
1. `adjustments/attest_path.py`; wire approve-and-send and record-external; ledger-matches read.
2. Tests: send recipient rules, record gating, pure matcher, posting refusal, route wiring.
3. Rollback: the field goes back to required; no table change.
