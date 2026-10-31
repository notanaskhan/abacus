---
id: TASK-2431
title: N-02-T28 Firm countersignature, reminders and envelope gates
spec: SPEC-381
acceptance_criteria: [AC-1]
risk_zone: red
status: in-review
epic: N-02
plan_key: N-02-T28
branch: n02-t28-countersign
worktree: /Users/ayushkbhatia/Accrued/abacus-s19b5
created: 2026-10-31
updated: 2026-10-31
---

## Objective
`POST /v1/envelopes/{id}/countersign/session` for the named firm signer only; human ad-hoc and bulk
remind (preview then send from the database template, policy cap); C13 gate kinds `envelope_send`
and `envelope_countersign`; HOME's Signatures out; envelope events on the activity catalogue.

Acceptance: "Margaret Okonkwo countersigns E14 and G3 is met, while any other partner is refused
with 403."

## Plan (red)
- `signatures/countersign.py`; routes in `contract.py`; registrations in `api.py`.
- No migration (signing sessions, events and policies exist).
- Tests: `tests/integration/test_n02t28_countersign.py` (end review).
- Rollback: revert; the routes answered 501.

## Progress log
- `2026-10-31` — Built on `n02-t28-countersign` off main 71d2e51d2. DEC-1479. The harness's
  countersigner is Daniel Reyes (N-02-T33's letter); the rule is the named signer, whoever it is.
