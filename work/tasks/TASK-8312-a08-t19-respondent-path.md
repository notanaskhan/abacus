---
id: TASK-8312
title: "A-08-T19: Respondent path (red)"
spec: docs/specs/SPEC-657-a08-audit-fieldwork-depth.md F5 (AC-7)
acceptance_criteria: [A-08-T19]
risk_zone: red
status: in-review
branch: a08-t19-respondent-path
worktree: /Users/ayushkbhatia/Accrued/abacus-s47g04
created: 2026-11-16
updated: 2026-11-16
plan_key: A-08-T19
---

## Objective
Respondent path (red).

## Plan (red)
1. `assurance/confirmations_respondent.py`: `submit` (a verified link principal only; one answer per confirmation; the server's difference; sealed name and explanation; the `responded` event by the link principal; status `responded`), `original_receipt`.
2. `assurance/confirmations_contract.py`: the live `POST /v1/confirm/{token}/response` resolves the page credential (cookie and CSRF header) and answers 409 `already_answered` with the original receipt id on a replay; fixture links unchanged.
3. Audit kind reviewed. Tests: `tests/unit/assurance/test_a08t19_respondent.py`. Rollback: revert; the `confirmation_links` control turns every link off.

## Progress log
- `2026-11-16` — Built in the S47 sequential stack (DEC-5309). Lint and pyright clean; the unit file ran green (3 tests). Partial: the live open view's render data (needs C7's authorization, A-08-T18 partial) still answers the uniform expired page; attachments through evidence uploads and ClamAV still 501; IP and user agent under the P-14 record type are not stored; the bank-account list is accepted but not stored. Gates and
  tests run once at the S47 end pass (build first, test last).
