---
id: TASK-2421
title: N-02-T27 E-file authorization policy and handwritten fallback
spec: SPEC-000  # the backlog row; N-02 §3.7, DF-11, C7 §4
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: red
status: in-review
epic: N-02
plan_key: N-02-T27
branch: s19-n02-t27
worktree: /Users/ayushkbhatia/Accrued/abacus-s19
created: 2026-10-31
updated: 2026-10-31
---

## Objective
`envelope_policies` for the e-file family (KBA required, SMS refused, three attempts, wet-signature
failure path, taxpayer before ERO); failures counted per signer; on the limit remote signing closes
for that signer with `verification_failed` and notifications; `POST signers/{sid}/wet-signature`
recording method handwritten; `GET /v1/envelope-policies` and a stricter-only PUT.

Acceptance: "Irene Kowal's third failure closes Irene's remote path with no retry, and Grace's
upload of the hand-signed 8879 completes E2 with method Handwritten."

## Plan (red)
- Migration `0564_wet_signature` (on 0563, T33's): `wet_recorded_by` with a person-only trigger;
  `verification_failed` needs at least one failure (a firm's stricter limit).
- `signatures/fallback.py`: policies (floor, stricter-only), KBA failure counting, the wet
  signature. Poll (`activities.envelope_poll`) and completion (`envelope_complete`) wired; the
  builder's e-file checks add `ero_before_taxpayer`; DocuSeal counts failures [verify].
- Routes live: wet signature, policies GET and PUT. C16 `envelope_signer_verification_failed`.
- SIG-01: "Upload signed 8879…" opens the sheet; chips carry `signer_id` and `locked`.
- Tests: `tests/integration/backfill/test_n02t27_handwritten_fallback.py` (end review).
- Rollback: the routes answer as before only by reverting; the migration's downgrade restores
  0292's check (fails if a firm's stricter limit closed a signer below three).

## Progress log
- `2026-10-31` — Built on `s19-n02-t27` off main 7d4def8e5; 0564 revises 0563 (T33, #903): merge
  T33 first. DEC-1469.
