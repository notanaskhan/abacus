---
id: TASK-8352
title: "T-07-T25: TXT-03 live: the beneficiaries screen on the API, routed under the 1041's Review"
spec: SPEC-656
acceptance_criteria: [AC-9, AC-10, AC-11]
risk_zone: amber
status: in-review
branch: txt03-live
worktree: /Users/ayushkbhatia/Accrued/abacus-s47g04
created: 2026-11-16
updated: 2026-11-16
plan_key: T-07-T25
---

## Objective
Spec section: SPEC-656 F9 to F11; handoff TXT-03. TXT-03 live: the beneficiaries screen on the API, routed under the 1041's Review.

## Plan (amber)
1. `screens/TXT-03/live.tsx`: `GET /v1/tax/returns/{id}/beneficiaries`; rows, totals and the tie-out line, the 65-day card, the release steps; Release K-1s… disabled with the server's reason; the handoff's words; figures through `count` and `pct`.
2. `/tax-returns/$returnId/review/beneficiaries` behind `tax.fiduciary_k1_release` (a package or Release opens TXP-12); the manifest gives TXT-03 its path. The gallery keeps the fixture artboards a to e.

## Progress log
- `2026-11-16` — Built in the S47 sequential stack. tsc, eslint and the route and TXT-03 tests (78) clean. Partial: the release confirm and Resend dialogs (TXP-12 hosts them), the trustee question card (its backend is partial), the a2/a3 frames and the parity tier. Gates and
  tests run once at the S47 end pass (build first, test last).
