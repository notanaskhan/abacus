---
id: TASK-8355
title: "A-08-T30: POR-17 respondent page at /confirm/$token on the live respondent routes"
spec: SPEC-none
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
branch: por17-respondent-page
worktree: /Users/ayushkbhatia/Accrued/abacus-s47g04
created: 2026-11-16
updated: 2026-11-16
plan_key: A-08-T30
---

## Objective
Spec section: A-08 F7 (respondent path); handoff POR-17 a–f. POR-17 respondent page at /confirm/$token on the live respondent routes.

## Plan (amber)
1. `screens/POR-17/` (`POR17`, copy verbatim from the handoff): `open` (request card with the client's authorization quoted, balance and invoices, bank accounts and add-account rows), `answered` (e), the uniform `expired` (d), the receipt (b).
2. The difference is code's, exact (bigint cents from `parseDecimal`), shown amber; Submit only with a choice, a verified code (the verify answer's `X-Abacus-CSRF` rides attachments and the response) and the attestation.
3. Public route `/confirm/$token` (the firm host, where `app_base_url` points the email link); manifest POR-17 live. Token passed to the page only.

## Progress log
- `2026-11-16` — Built in the S47 sequential stack. tsc, eslint, the POR-17 tests (5: d, e, a, the difference, b with the CSRF on submit) and the route tests clean. Partial: the 390 reflow, the firm's mark and address (no unauthenticated read), the short client name ('Granite Peak') where the API gives the full one, the expired copy without the firm name (DV-7 uniform answer), bank account type folded into the description (no type field), UploadRow upload progress. Gates and
  tests run once at the S47 end pass (build first, test last).
