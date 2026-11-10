---
id: TASK-3396
title: N-04-T16 a notice reaches Approved, signature and Awaiting IRS outside the seed
spec: SPEC-000  # row (N-04-T16)
acceptance_criteria: [AC-1]
risk_zone: red
status: in-review
epic: N-04
plan_key: N-04-T16
branch: s28p-n04-t16-chain
worktree: /Users/ayushkbhatia/Accrued/abacus-s28
created: 2026-11-08
updated: 2026-11-08
---

## Objective
DEC-2392 left signing, completion and mark sent with real readiness unrun. Run the chain through the services against the loaded notices slice, without patching readiness.

## Plan
- Status moves the product never made (only the seed loader walked them): Run moves classified to analyzing, drafting moves to response_drafted, a new version moves approved back to response_drafted, and the partner's L4 sign-off on the response moves response_drafted to approved (`sign_off.recorded` subscriber).
- `send_for_signature` requires the partner's current L4 sign-off, not only that nothing refuses one.
- `on_envelope_completed` and `on_review_decision` read the engagement from the notice (the response has no such column).
- Catalogue `notice.approved`.
- Rollback: revert; no migration.

## Progress log
- 2026-11-08: built. `tests/integration/test_n04t21_load.py` chain extended: Run, draft, decision, regenerate, edit, refused send without sign-off, L1 and L4 sign-offs, Approved, send for signature, sealed letter, envelope completed (DocuSeal's webhook stood in by setting the envelope's status), readiness read for real, mark sent, Awaiting IRS: 4 pass on Postgres. `tests/unit/notices/test_s28_notice_status_moves.py` (5). Unit notices, audit_trail, worker, contracts/notices: 632 pass; 3 fail on main's own reds (two `intake_sources.flag_enabled` after S29 retired the flag, the worker routing pin).

## Decisions made during this task
DEC-2395
