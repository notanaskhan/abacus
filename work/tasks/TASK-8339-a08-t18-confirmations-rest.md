---
id: TASK-8339
title: "A-08-T18: Confirmations, the rest: C7 authorization, emailed links at delivery, follow-up prompts, revoke, exception prefill"
spec: SPEC-657
acceptance_criteria: [AC-6]
risk_zone: red
status: in-review
branch: a08-t18-confirmations-rest
worktree: /Users/ayushkbhatia/Accrued/abacus-s47g04
created: 2026-11-16
updated: 2026-11-16
plan_key: A-08-T18
---

## Objective
Spec section: SPEC-657 F4 (AC-6.3 to AC-6.6); A-08 §4.7. Confirmations, the rest: C7 authorization, emailed links at delivery, follow-up prompts, revoke, exception prefill.

## Plan (red)
1. 0932: `confirmation_authorizations` and `confirmation_authorization_items` (insert-only items; `envelope_id`, `completed_at` the only updates); `confirmation_events` gains `authorized`, `second_request_due`, `no_response_due`.
2. `assurance/confirmations_authorization.py`: one C7 envelope (purpose `confirmation_authorization`, general) per request over the firm's authorization letter (an evidence version on the engagement) for the client's named signer; the C7 source and its draft; `envelope.completed` returns the covered confirmations to Draft (authorized). Send now needs Draft.
3. `communications/respondent_links.py`: `confirmation.link_requested` delivers the respondent's link: assurance's registered minter issues the link principal at delivery and returns the token in memory only; the firm's `confirmation_request` template; the respondent audience gate (DEC-953).
4. `assurance/confirmations_follow_up.py`: `ConfirmationFollowUpWorkflow`, a daily platform Schedule that prompts the sender once per due step (never acts); four team notification kinds (A-08 §4.7).
5. Revoke-link (it called send before: fixed) and SHL-15's exception prefill (finding at or above CT, else misstatement).

## Progress log
- `2026-11-16` — Built in the S47 sequential stack (DEC-5324). Lint, pyright and the banned patterns clean; the app imports; client regenerated. Partial: POR-17 (the respondent's page in the front end) is still planned; the confirmation second-request email template (A-08 §4.7 external) is not registered. Gates and
  tests run once at the S47 end pass (build first, test last).
