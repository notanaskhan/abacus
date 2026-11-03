---
id: TASK-3214
title: A-06-T14 review extensions for AUD-17 (re-review request, note bands)
spec: SPEC-642
acceptance_criteria: [AC-9]
risk_zone: red
status: in-review
epic: A-06
plan_key: A-06-T14
branch: s26-a06-t14 (stacked on s26-a06-t13)
worktree: /Users/ayushkbhatia/Accrued/abacus-s26
created: 2026-11-03
updated: 2026-11-03
---

## Objective
"Reopen returns a cleared note to Open and blocks L2+ again, re-review notifies the stale signer,
and the list returns 2 + 1 + 11 = 14 for Northwind."

## Plan (red)
- Matrix: `sign_off.request_re_review` (EP, manager, senior; agent and system deny).
- `review/re_review.py`:
  - `request_re_review`: stale sign-offs only (409 `not_stale`); audited;
    `sign_off.re_review_requested` → C16 `sign_off_re_review` to the signer;
  - `bands_of`.
- Routes: `POST /v1/sign-offs/{id}/request-re-review` and `GET /v1/review-notes/bands`.
- Reopen is C3's existing `reopened` note event (P-04-T21); an open note already blocks L2+
  (R-SO-4).
- Test: `tests/unit/review/test_a06t14_re_review.py`.

## Progress log
- 2026-11-03: built. Via-Agent reply attribution reads the note event's actor kind the way C3
  already labels agent rows; no change was needed. Tests at the S26 end review.

## Decisions made during this task
DEC-2214.
