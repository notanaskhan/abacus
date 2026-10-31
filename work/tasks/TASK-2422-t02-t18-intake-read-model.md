---
id: TASK-2422
title: T-02-T18 Intake read model and actions (TAX-03)
spec: SPEC-000  # the backlog row; T-02 §3.4, DV-6, DV-7
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
epic: T-02
plan_key: T-02-T18
branch: s19-t02-t18
worktree: /Users/ayushkbhatia/Accrued/abacus-s19
created: 2026-10-31
updated: 2026-10-31
---

## Objective
`GET /v1/tax-returns/{id}/intake` composing the C5 binder, categories, requests, fulfilments and
channels, N-01 waiting inbox files with consent- and clearance-gated matcher suggestions, the
`wrong_tax_year` ignore reason, the questionnaire summary and K-1 hand-off rows; request
acceptance behind Approve Document.

Acceptance: "Feld intake reads 5 of 7 and a taxpayer without both consents gets no suggestion and
causes zero gateway calls."

## Plan (amber)
- `tax/intake.py` composing through other modules' `api.py` only (no table reads outside tax).
- New reads: `requests.binder_card`, `requests.work_item_questionnaires`,
  `communications.waiting_for_client`, `evidence.attachment_tax_years`; `agents.api.stage_for`
  exported; `card_candidates` exported.
- Contract additions on `TaxReturnIntakeOut` (defaults); route live; `make regenerate`.
- Tests: `tests/integration/test_t02t18_intake.py` (end review).
- Rollback: revert; the route answered 501 before.

## Progress log
- `2026-10-31` — Built on `s19-t02-t18` off main 7d4def8e5. DEC-1470. Upload intents (portal
  uploads in flight) are not composed: no upload-intent table exists yet; the live row waits on
  P-06's polling (T-02-T19).
